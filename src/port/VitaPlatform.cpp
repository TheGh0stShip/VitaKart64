#include "VitaPlatform.h"

#include <algorithm>
#include <cmath>
#include <cstdio>

#ifdef __vita__
#include <SDL2/SDL.h>
#include <imgui.h>
#include <libultraship.h>
#include "fast/Fast3dWindow.h"
#include <psp2/power.h>
#include "ship/Context.h"
#include "ship/window/Window.h"
#endif

#ifndef VITAKART_FRAME_HITCH_LOG
#define VITAKART_FRAME_HITCH_LOG 0
#endif

#ifndef VITAKART_FRAME_HITCH_LOG_MS
#define VITAKART_FRAME_HITCH_LOG_MS 18
#endif

#if VITAKART_FRAME_HITCH_LOG_MS <= 0
#undef VITAKART_FRAME_HITCH_LOG_MS
#define VITAKART_FRAME_HITCH_LOG_MS 18
#endif

namespace VitaPlatform {

#ifdef __vita__
namespace {

constexpr int ArmClock = 500;
constexpr int BusClock = 222;
constexpr int GpuClock = 222;
constexpr int GpuXbarClock = 166;
constexpr int TargetFps = 60;
constexpr float DefaultRenderScale = 1.0f / 2.0f;
constexpr float MinimumRenderScale = 1.0f / 2.0f;

struct RuntimeState {
    bool initialized = false;
    bool suspended = false;
    Telemetry telemetry;
    uint64_t lastFrameCounter = 0;
    uint64_t lastTelemetryCounter = 0;
    float frameTimeEma = 16.6667f;
    int slowFrameCount = 0;
    int fastFrameCount = 0;
    int activeFingers = 0;
    int peakFingers = 0;
    uint32_t gestureStartMs = 0;
};

RuntimeState State;

void ResetRuntimeEvidence() {
#ifdef __vita__
    std::remove("ux0:data/vitakart64/frame-hitches.log");
    std::remove("ux0:data/vitakart64/texture-misses.log");
    std::remove("ux0:data/vitakart64/preload-summary.txt");
    std::remove("ux0:data/vitakart64/preload-reentry.txt");
#endif
}

#if defined(__vita__) && VITAKART_FRAME_HITCH_LOG
FILE* sFrameHitchLog = nullptr;
uint32_t sFrameHitchCount = 0;

void LogFrameHitch(float sampleMs) {
    if (sampleMs < static_cast<float>(VITAKART_FRAME_HITCH_LOG_MS)) {
        return;
    }

    if (sFrameHitchLog == nullptr) {
        sFrameHitchLog = std::fopen("ux0:data/vitakart64/frame-hitches.log", "w");
        if (sFrameHitchLog == nullptr) {
            return;
        }
        std::fprintf(sFrameHitchLog, "# Vita Kart 64 frame hitch log\n");
        std::fprintf(sFrameHitchLog, "# threshold_ms=%d\n", VITAKART_FRAME_HITCH_LOG_MS);
    }

    sFrameHitchCount++;
    std::fprintf(sFrameHitchLog, "tick_ms=%u frame_ms=%.3f ema_ms=%.3f fps=%.2f\n", SDL_GetTicks(), sampleMs,
                 State.frameTimeEma, State.telemetry.framesPerSecond);
    if ((sFrameHitchCount & 15U) == 0) {
        std::fflush(sFrameHitchLog);
    }
}

void CloseFrameHitchLog() {
    if (sFrameHitchLog == nullptr) {
        return;
    }
    std::fflush(sFrameHitchLog);
    std::fclose(sFrameHitchLog);
    sFrameHitchLog = nullptr;
}
#else
void LogFrameHitch(float) {}
void CloseFrameHitchLog() {}
#endif

void SetRenderScale(float scale) {
    scale = std::clamp(scale, MinimumRenderScale, DefaultRenderScale);
    CVarSetFloat("gInternalResolution", scale);
    State.telemetry.internalResolution = scale;

    auto context = Ship::Context::GetInstance();
    if (context != nullptr && context->GetWindow() != nullptr) {
        context->GetWindow()->SetResolutionMultiplier(scale);
    }
}

void UpdateTelemetry() {
    State.telemetry.batteryPercent = scePowerGetBatteryLifePercent();
    State.telemetry.batteryMinutes = scePowerGetBatteryLifeTime();
    State.telemetry.batteryTemperature = scePowerGetBatteryTemp();
    State.telemetry.charging = scePowerIsBatteryCharging() == SCE_TRUE;
}

void ToggleTelemetryHud() {
    CVarSetInteger(TelemetryHudCVar, !CVarGetInteger(TelemetryHudCVar, 0));
    CVarSave();
}

} // namespace

void Initialize() {
    if (State.initialized) {
        return;
    }

    State.initialized = true;
    State.lastFrameCounter = SDL_GetPerformanceCounter();
    State.lastTelemetryCounter = State.lastFrameCounter;
    ResetRuntimeEvidence();
    ApplyMaxPerformance(true);
    UpdateTelemetry();
}

void ApplyBootClocks() {
    scePowerSetArmClockFrequency(ArmClock);
    scePowerSetBusClockFrequency(BusClock);
    scePowerSetGpuClockFrequency(GpuClock);
    scePowerSetGpuXbarClockFrequency(GpuXbarClock);
}

void Shutdown() {
    if (!State.initialized) {
        return;
    }
    CVarSave();
    CloseFrameHitchLog();
    State.initialized = false;
}

void ApplyMaxPerformance(bool resetRenderingSettings) {
    ApplyBootClocks();

    State.telemetry.armClock = ArmClock;
    State.telemetry.busClock = BusClock;
    State.telemetry.gpuClock = GpuClock;
    State.telemetry.gpuXbarClock = GpuXbarClock;

    CVarSetInteger("gInterpolationFPS", TargetFps);
    CVarSetInteger("gMatchRefreshRate", 0);
    CVarSetInteger("gVsyncEnabled", 1);
    CVarSetInteger("gMSAAValue", 1);
    CVarSetInteger("gTextureFilter", 1);
    CVarSetInteger("gVitaAdaptiveResolution", 0);
    CVarSetInteger("gEnhancements.Mods.AlternateAssets", 0);
    CVarSetInteger("gAdvancedResolution.Enabled", 0);
    CVarSetInteger("gLowResMode", 0);
    CVarSetInteger("gEnableMultiViewports", 0);

    if (resetRenderingSettings) {
        CVarSetFloat("gVitaAdaptiveResolutionFloor", MinimumRenderScale);
        CVarSetInteger("gControlNav", 0);
        SetRenderScale(DefaultRenderScale);

        auto context = Ship::Context::GetInstance();
        if (context != nullptr && context->GetWindow() != nullptr) {
            context->GetWindow()->SetMsaaLevel(1);
            if (auto fast3dWindow = dynamic_cast<Fast::Fast3dWindow*>(context->GetWindow().get())) {
                fast3dWindow->SetTextureFilter(Fast::FILTER_LINEAR);
            }
        }
    }

    State.slowFrameCount = 0;
    State.fastFrameCount = 0;
}

void OnFramePresented() {
    if (!State.initialized || State.suspended) {
        return;
    }

    const uint64_t now = SDL_GetPerformanceCounter();
    const uint64_t frequency = SDL_GetPerformanceFrequency();
    if (State.lastFrameCounter == 0 || frequency == 0) {
        State.lastFrameCounter = now;
        return;
    }

    const float sampleMs = static_cast<float>(now - State.lastFrameCounter) * 1000.0f /
                           static_cast<float>(frequency);
    State.lastFrameCounter = now;

    if (sampleMs >= 4.0f && sampleMs <= 100.0f) {
        State.frameTimeEma += (sampleMs - State.frameTimeEma) * 0.06f;
        State.telemetry.frameTimeMs = State.frameTimeEma;
        State.telemetry.framesPerSecond = 1000.0f / State.frameTimeEma;
        LogFrameHitch(sampleMs);
    }

    if (now - State.lastTelemetryCounter >= frequency * 5) {
        State.lastTelemetryCounter = now;
        UpdateTelemetry();
    }

    if (!CVarGetInteger(AdaptiveResolutionCVar, 1)) {
        State.slowFrameCount = 0;
        State.fastFrameCount = 0;
        return;
    }

    if (State.frameTimeEma > 17.1f) {
        State.slowFrameCount++;
        State.fastFrameCount = 0;
    } else if (State.frameTimeEma < 16.0f) {
        State.fastFrameCount++;
        State.slowFrameCount = 0;
    } else {
        State.slowFrameCount = std::max(0, State.slowFrameCount - 1);
        State.fastFrameCount = std::max(0, State.fastFrameCount - 1);
    }

    const float floor = std::clamp(CVarGetFloat(AdaptiveResolutionFloorCVar, MinimumRenderScale),
                                   MinimumRenderScale, DefaultRenderScale);
    const float current = CVarGetFloat("gInternalResolution", DefaultRenderScale);

    if (State.slowFrameCount >= 30 && current > floor + 0.001f) {
        SetRenderScale(std::max(floor, current - 0.025f));
        State.slowFrameCount = 0;
        State.fastFrameCount = 0;
    } else if (State.fastFrameCount >= 1200 && current < DefaultRenderScale - 0.001f) {
        SetRenderScale(std::min(DefaultRenderScale, current + 0.025f));
        State.slowFrameCount = 0;
        State.fastFrameCount = 0;
    }
}

void HandleEvent(const SDL_Event& event) {
    if (!State.initialized) {
        return;
    }

    switch (event.type) {
        case SDL_APP_WILLENTERBACKGROUND:
            State.suspended = true;
            CVarSave();
            SDL_PauseAudio(1);
            break;
        case SDL_APP_DIDENTERFOREGROUND:
            SDL_PauseAudio(0);
            State.suspended = false;
            State.lastFrameCounter = SDL_GetPerformanceCounter();
            State.frameTimeEma = 16.6667f;
            ApplyMaxPerformance(false);
            break;
        case SDL_APP_TERMINATING:
            CVarSave();
            CloseFrameHitchLog();
            break;
        case SDL_FINGERDOWN:
            if (State.activeFingers == 0) {
                State.gestureStartMs = event.tfinger.timestamp;
                State.peakFingers = 0;
            }
            State.activeFingers++;
            State.peakFingers = std::max(State.peakFingers, State.activeFingers);
            break;
        case SDL_FINGERUP:
            State.activeFingers = std::max(0, State.activeFingers - 1);
            if (State.activeFingers == 0 && State.peakFingers == 2 &&
                CVarGetInteger(TouchShortcutsCVar, 1) &&
                event.tfinger.timestamp - State.gestureStartMs <= 450) {
                ToggleTelemetryHud();
            }
            break;
        default:
            break;
    }
}

void DrawOverlay() {
    if (!State.initialized || !CVarGetInteger(TelemetryHudCVar, 0)) {
        return;
    }

    const ImGuiIO& io = ImGui::GetIO();
    ImGui::SetNextWindowPos(ImVec2(io.DisplaySize.x - 8.0f, 8.0f), ImGuiCond_Always, ImVec2(1.0f, 0.0f));
    ImGui::SetNextWindowBgAlpha(0.78f);
    const ImGuiWindowFlags flags = ImGuiWindowFlags_AlwaysAutoResize | ImGuiWindowFlags_NoDecoration |
                                   ImGuiWindowFlags_NoInputs | ImGuiWindowFlags_NoNav |
                                   ImGuiWindowFlags_NoSavedSettings | ImGuiWindowFlags_NoFocusOnAppearing;
    if (ImGui::Begin("##VitaKart64Telemetry", nullptr, flags)) {
        ImGui::TextColored(ImVec4(0.20f, 0.90f, 0.92f, 1.0f), "VITA KART 64");
        ImGui::SameLine();
        ImGui::TextDisabled("MAX 60");
        ImGui::Text("%4.1f FPS  %4.1f ms  %3.0f%% res", State.telemetry.framesPerSecond,
                    State.telemetry.frameTimeMs, State.telemetry.internalResolution * 100.0f);
        if (State.telemetry.batteryPercent >= 0) {
            ImGui::Text("Battery %d%%%s  %2.1f C", State.telemetry.batteryPercent,
                        State.telemetry.charging ? " +" : "", State.telemetry.batteryTemperature / 100.0f);
        }
    }
    ImGui::End();
}

const Telemetry& GetTelemetry() {
    return State.telemetry;
}

std::string GetStatusText() {
    char status[256];
    const char* powerState = State.telemetry.charging ? "charging" : "on battery";
    if (State.telemetry.batteryPercent < 0) {
        std::snprintf(status, sizeof(status), "Max clocks | 60 FPS target | %.0f%% internal resolution",
                      State.telemetry.internalResolution * 100.0f);
    } else {
        std::snprintf(status, sizeof(status),
                      "Max clocks | %.1f FPS | %.0f%% internal resolution\nBattery %d%%, %s, %.1f C, %d min remaining",
                      State.telemetry.framesPerSecond, State.telemetry.internalResolution * 100.0f,
                      State.telemetry.batteryPercent, powerState, State.telemetry.batteryTemperature / 100.0f,
                      State.telemetry.batteryMinutes);
    }
    return status;
}

#else

namespace {
Telemetry EmptyTelemetry;
}

void Initialize() {}
void Shutdown() {}
void ApplyMaxPerformance(bool) {}
void OnFramePresented() {}
void HandleEvent(const SDL_Event&) {}
void DrawOverlay() {}
const Telemetry& GetTelemetry() { return EmptyTelemetry; }
std::string GetStatusText() { return "Vita telemetry unavailable"; }

#endif

} // namespace VitaPlatform
