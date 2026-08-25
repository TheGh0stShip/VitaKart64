#pragma once

#include <string>

union SDL_Event;

namespace VitaPlatform {

struct Telemetry {
    int batteryPercent = -1;
    int batteryMinutes = -1;
    int batteryTemperature = -1;
    bool charging = false;
    float framesPerSecond = 0.0f;
    float frameTimeMs = 0.0f;
    float internalResolution = 1.0f / 3.0f;
    int armClock = 500;
    int busClock = 222;
    int gpuClock = 222;
    int gpuXbarClock = 166;
};

inline constexpr const char* AdaptiveResolutionCVar = "gVitaAdaptiveResolution";
inline constexpr const char* AdaptiveResolutionFloorCVar = "gVitaAdaptiveResolutionFloor";
inline constexpr const char* TelemetryHudCVar = "gVitaTelemetryHud";
inline constexpr const char* TouchShortcutsCVar = "gVitaTouchShortcuts";

void Initialize();
void ApplyBootClocks();
void Shutdown();
void ApplyMaxPerformance(bool resetRenderingSettings = true);
void OnFramePresented();
void HandleEvent(const SDL_Event& event);
void DrawOverlay();
const Telemetry& GetTelemetry();
std::string GetStatusText();

} // namespace VitaPlatform
