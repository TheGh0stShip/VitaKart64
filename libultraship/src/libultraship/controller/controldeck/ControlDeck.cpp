#include "libultraship/controller/controldeck/ControlDeck.h"

#include "ship/Context.h"
#include "libultraship/controller/controldevice/controller/Controller.h"
#include "libultraship/controller/controldevice/controller/mapping/ControllerDefaultMappings.h"
#include "ship/utils/StringHelper.h"
#include <imgui.h>
#include "ship/controller/controldevice/controller/mapping/mouse/WheelHandler.h"
#ifdef __vita__
#include <vitasdk.h>
#endif

namespace LUS {
#ifdef __vita__
namespace {
constexpr int kVitaAnalogCenter = 128;
constexpr int kVitaAnalogDeadzone = 18;
constexpr int kN64StickMax = 80;
constexpr int kCButtonThreshold = 72;

int8_t VitaAnalogToN64Stick(uint8_t value, bool invert) {
    int centered = static_cast<int>(value) - kVitaAnalogCenter;
    if (invert) {
        centered = -centered;
    }

    if (centered > -kVitaAnalogDeadzone && centered < kVitaAnalogDeadzone) {
        return 0;
    }

    int scaled = centered * kN64StickMax / 127;
    if (scaled > kN64StickMax) {
        scaled = kN64StickMax;
    } else if (scaled < -kN64StickMax) {
        scaled = -kN64StickMax;
    }

    return static_cast<int8_t>(scaled);
}

void WriteNativeVitaPad(OSContPad* pad) {
    SceCtrlData ctrl = {};
    if (sceCtrlPeekBufferPositive(0, &ctrl, 1) <= 0) {
        return;
    }

    OSContPad& port0 = pad[0];

    if (ctrl.buttons & SCE_CTRL_CROSS) {
        port0.button |= BTN_A;
    }
    if (ctrl.buttons & SCE_CTRL_SQUARE) {
        port0.button |= BTN_B;
    }
    if (ctrl.buttons & SCE_CTRL_START) {
        port0.button |= BTN_START;
    }
    if (ctrl.buttons & SCE_CTRL_SELECT) {
        port0.button |= BTN_L;
    }
    if (ctrl.buttons & SCE_CTRL_LTRIGGER) {
        port0.button |= BTN_Z;
    }
    if (ctrl.buttons & SCE_CTRL_RTRIGGER) {
        port0.button |= BTN_R;
    }
    if (ctrl.buttons & SCE_CTRL_TRIANGLE) {
        port0.button |= BTN_CLEFT;
    }
    if (ctrl.buttons & SCE_CTRL_CIRCLE) {
        port0.button |= BTN_CDOWN;
    }
    if (ctrl.buttons & SCE_CTRL_UP) {
        port0.button |= BTN_DUP;
    }
    if (ctrl.buttons & SCE_CTRL_DOWN) {
        port0.button |= BTN_DDOWN;
    }
    if (ctrl.buttons & SCE_CTRL_LEFT) {
        port0.button |= BTN_DLEFT;
    }
    if (ctrl.buttons & SCE_CTRL_RIGHT) {
        port0.button |= BTN_DRIGHT;
    }

    port0.stick_x = VitaAnalogToN64Stick(ctrl.lx, false);
    port0.stick_y = VitaAnalogToN64Stick(ctrl.ly, true);
    port0.right_stick_x = VitaAnalogToN64Stick(ctrl.rx, false);
    port0.right_stick_y = VitaAnalogToN64Stick(ctrl.ry, true);

    const int rightX = static_cast<int>(ctrl.rx) - kVitaAnalogCenter;
    const int rightY = static_cast<int>(ctrl.ry) - kVitaAnalogCenter;
    if (rightX > kCButtonThreshold) {
        port0.button |= BTN_CRIGHT;
    } else if (rightX < -kCButtonThreshold) {
        port0.button |= BTN_CLEFT;
    }
    if (rightY > kCButtonThreshold) {
        port0.button |= BTN_CDOWN;
    } else if (rightY < -kCButtonThreshold) {
        port0.button |= BTN_CUP;
    }
}
} // namespace
#endif

ControlDeck::ControlDeck(std::vector<CONTROLLERBUTTONS_T> additionalBitmasks,
                         std::shared_ptr<Ship::ControllerDefaultMappings> controllerDefaultMappings,
                         std::unordered_map<CONTROLLERBUTTONS_T, std::string> buttonNames)
    : Ship::ControlDeck(additionalBitmasks, controllerDefaultMappings, buttonNames), mPads(nullptr) {
    std::vector<CONTROLLERBUTTONS_T> bitmasks;
    for (auto [bitmask, name] : buttonNames) {
        bitmasks.push_back(bitmask);
    }
    bitmasks.insert(bitmasks.end(), additionalBitmasks.begin(), additionalBitmasks.end());
    for (int32_t i = 0; i < MAXCONTROLLERS; i++) {
        mPorts.push_back(std::make_shared<Ship::ControlPort>(i, std::make_shared<Controller>(i, bitmasks)));
    }
}

ControlDeck::ControlDeck(std::vector<CONTROLLERBUTTONS_T> additionalBitmasks)
    : ControlDeck(additionalBitmasks, std::make_shared<LUS::ControllerDefaultMappings>(),
                  std::unordered_map<CONTROLLERBUTTONS_T, std::string>({
                      { BTN_A, "A" },
                      { BTN_B, "B" },
                      { BTN_L, "L" },
                      { BTN_R, "R" },
                      { BTN_Z, "Z" },
                      { BTN_START, "Start" },
                      { BTN_CLEFT, "CLeft" },
                      { BTN_CRIGHT, "CRight" },
                      { BTN_CUP, "CUp" },
                      { BTN_CDOWN, "CDown" },
                      { BTN_DLEFT, "DLeft" },
                      { BTN_DRIGHT, "DRight" },
                      { BTN_DUP, "DUp" },
                      { BTN_DDOWN, "DDown" },
                  })) {
}

ControlDeck::ControlDeck() : ControlDeck(std::vector<CONTROLLERBUTTONS_T>()) {
}

OSContPad* ControlDeck::GetPads() {
    return mPads;
}

void ControlDeck::WriteToPad(void* pad) {
    WriteToOSContPad((OSContPad*)pad);
}

void ControlDeck::WriteToOSContPad(OSContPad* pad) {
#ifdef __vita__
    if (pad == nullptr) {
        return;
    }

    if (AllGameInputBlocked()) {
        return;
    }

    mPads = pad;
    WriteNativeVitaPad(pad);
    return;
#else
    SDL_PumpEvents();
    Ship::WheelHandler::GetInstance()->Update();

    if (AllGameInputBlocked()) {
        return;
    }

    mPads = pad;

    for (size_t i = 0; i < mPorts.size(); i++) {
        const std::shared_ptr<Ship::Controller> controller = mPorts[i]->GetConnectedController();

        if (controller != nullptr) {
            controller->ReadToPad(&pad[i]);
        }
    }
#endif
}
} // namespace LUS
