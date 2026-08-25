#include "ship/audio/Audio.h"

#ifdef __APPLE__
#include "ship/audio/CoreAudioAudioPlayer.h"
#endif

#ifndef __vita__
#include "ship/audio/OpenALAudioPlayer.h"
#endif

#include "ship/Context.h"
#include "ship/controller/controldeck/ControlDeck.h"

namespace Ship {

Audio::~Audio() {
    SPDLOG_TRACE("destruct audio");
}

void Audio::InitAudioPlayer() {
#ifdef __vita__
    // Vita uses the hardware-backed implementation in SDLAudioPlayer. Never
    // honor a stale "null" backend left behind by an older failed build.
    mAudioBackend = AudioBackend::SDL;
#endif

    switch (GetCurrentAudioBackend()) {
#ifdef _WIN32
        case AudioBackend::WASAPI:
            mAudioPlayer = std::make_shared<WasapiAudioPlayer>(this->mAudioSettings);
            break;
#endif
#ifdef __APPLE__
        case AudioBackend::COREAUDIO:
            mAudioPlayer = std::make_shared<CoreAudioAudioPlayer>(this->mAudioSettings);
            break;
#endif
        case AudioBackend::SDL:
            mAudioPlayer = std::make_shared<SDLAudioPlayer>(this->mAudioSettings);
            break;
#ifndef __vita__
        case AudioBackend::OAL:
            mAudioPlayer = std::make_shared<OpenALAudioPlayer>(this->mAudioSettings);
            break;
#endif
        default:
            mAudioPlayer = std::make_shared<NullAudioPlayer>(this->mAudioSettings);
            break;
    }

    if (mAudioPlayer && !mAudioPlayer->Init()) {
        // Failed to initialize system audio player.
#ifdef __vita__
        // Keep the selected backend intact so a transient device failure can
        // never permanently save muted audio to the configuration.
        SPDLOG_ERROR("Vita native audio initialization failed");
#else
        // Fallback to OpenAL if the native system player does not work.
        SetCurrentAudioBackend(AudioBackend::OAL);
#endif
    }
}

void Audio::Init() {
    mAvailableAudioBackends = std::make_shared<std::vector<AudioBackend>>();
#ifdef _WIN32
    mAvailableAudioBackends->push_back(AudioBackend::WASAPI);
#endif
#ifdef __APPLE__
    mAvailableAudioBackends->push_back(AudioBackend::COREAUDIO);
#endif
#ifdef __vita__
    mAudioSettings.ChannelSetting = AudioChannelsSetting::audioStereo;
    mAvailableAudioBackends->push_back(AudioBackend::SDL);
#else
    mAvailableAudioBackends->push_back(AudioBackend::SDL);
    mAvailableAudioBackends->push_back(AudioBackend::OAL);
    mAvailableAudioBackends->push_back(AudioBackend::NUL);
#endif

#ifdef __vita__
    SetCurrentAudioBackend(AudioBackend::SDL);
#else
    SetCurrentAudioBackend(Context::GetInstance()->GetConfig()->GetCurrentAudioBackend());
#endif
}

std::shared_ptr<AudioPlayer> Audio::GetAudioPlayer() {
    return mAudioPlayer;
}

AudioBackend Audio::GetCurrentAudioBackend() {
    return mAudioBackend;
}

void Audio::SetCurrentAudioBackend(AudioBackend backend) {
#ifdef __vita__
    backend = AudioBackend::SDL;
#endif
    mAudioBackend = backend;
    Context::GetInstance()->GetConfig()->SetCurrentAudioBackend(GetCurrentAudioBackend());
    Context::GetInstance()->GetConfig()->Save();

    InitAudioPlayer();
}

std::shared_ptr<std::vector<AudioBackend>> Audio::GetAvailableAudioBackends() {
    return mAvailableAudioBackends;
}

void Audio::SetAudioChannels(AudioChannelsSetting channels) {
#ifdef __vita__
    channels = AudioChannelsSetting::audioStereo;
#endif
    if (mAudioSettings.ChannelSetting != channels) {
        mAudioSettings.ChannelSetting = channels;
        // Reinitialize the existing audio player with the new channel configuration
        if (mAudioPlayer) {
            mAudioPlayer->SetAudioChannels(channels);
        }
    }
}

AudioChannelsSetting Audio::GetAudioChannels() const {
    return mAudioSettings.ChannelSetting;
}

} // namespace Ship
