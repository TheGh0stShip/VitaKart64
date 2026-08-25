#include "ship/audio/SDLAudioPlayer.h"
#include <algorithm>
#include <array>
#include <cstring>
#include <limits>
#include <spdlog/spdlog.h>
#ifdef __vita__
#include <psp2/audioout.h>
#endif

namespace Ship {

#ifdef __vita__
namespace {
constexpr int32_t kPreferredOutputRate = 32000;
constexpr int32_t kFallbackOutputRate = 48000;

struct VitaResamplerState {
    int32_t outputRate = kPreferredOutputRate;
    std::vector<int16_t> scratch;
    uint32_t phase = 0;
    int16_t previousFrame[2] = { 0, 0 };
    bool havePreviousFrame = false;
};

VitaResamplerState gVitaResampler;
} // namespace
#endif

SDLAudioPlayer::~SDLAudioPlayer() {
    SPDLOG_TRACE("destruct SDL audio player");
    DoClose();
#ifndef __vita__
    SDL_QuitSubSystem(SDL_INIT_AUDIO);
#endif
}

void SDLAudioPlayer::DoClose() {
#ifdef __vita__
    {
        std::lock_guard<std::mutex> lock(mQueueMutex);
        mRunning = false;
    }
    mQueueReady.notify_all();

    if (mOutputThread.joinable()) {
        mOutputThread.join();
    }

    if (mPort >= 0) {
        sceAudioOutOutput(mPort, nullptr);
        sceAudioOutReleasePort(mPort);
        mPort = -1;
    }

    std::lock_guard<std::mutex> lock(mQueueMutex);
    mQueue.clear();
    mReadFrame = 0;
    mWriteFrame = 0;
    mQueuedFrames = 0;
    gVitaResampler.scratch.clear();
    gVitaResampler.phase = 0;
    gVitaResampler.previousFrame[0] = 0;
    gVitaResampler.previousFrame[1] = 0;
    gVitaResampler.havePreviousFrame = false;
#else
    if (mDevice != 0) {
        // Pause playback first
        SDL_PauseAudioDevice(mDevice, 1);
        // Clear any queued audio to prevent glitches when reopening
        SDL_ClearQueuedAudio(mDevice);
        SDL_CloseAudioDevice(mDevice);
        mDevice = 0;
    }
#endif
}

bool SDLAudioPlayer::DoInit() {
#ifdef __vita__
    DoClose();
    mNumChannels = 2;
    gVitaResampler.outputRate = kPreferredOutputRate;
    mPort = sceAudioOutOpenPort(SCE_AUDIO_OUT_PORT_TYPE_BGM, static_cast<int>(OutputFrames),
                                gVitaResampler.outputRate,
                                SCE_AUDIO_OUT_MODE_STEREO);
    if (mPort < 0) {
        const int bgmError = mPort;
        gVitaResampler.outputRate = kFallbackOutputRate;
        mPort = sceAudioOutOpenPort(SCE_AUDIO_OUT_PORT_TYPE_MAIN, static_cast<int>(OutputFrames),
                                    gVitaResampler.outputRate, SCE_AUDIO_OUT_MODE_STEREO);
        if (mPort < 0) {
            SPDLOG_ERROR("sceAudioOutOpenPort failed (BGM {:#x}, MAIN {:#x})", static_cast<uint32_t>(bgmError),
                         static_cast<uint32_t>(mPort));
            return false;
        }
    }

    int volume[2] = { SCE_AUDIO_VOLUME_0DB, SCE_AUDIO_VOLUME_0DB };
    sceAudioOutSetVolume(
        mPort,
        static_cast<SceAudioOutChannelFlag>(SCE_AUDIO_VOLUME_FLAG_L_CH | SCE_AUDIO_VOLUME_FLAG_R_CH), volume);

    {
        std::lock_guard<std::mutex> lock(mQueueMutex);
        mQueue.assign(QueueFrames * mNumChannels, 0);
        gVitaResampler.scratch.clear();
        gVitaResampler.scratch.reserve(OutputFrames * 3 * mNumChannels);
        mReadFrame = 0;
        mWriteFrame = 0;
        mQueuedFrames = 0;
        gVitaResampler.phase = 0;
        gVitaResampler.previousFrame[0] = 0;
        gVitaResampler.previousFrame[1] = 0;
        gVitaResampler.havePreviousFrame = false;
        mRunning = true;
    }

    try {
        mOutputThread = std::thread(&SDLAudioPlayer::OutputLoop, this);
    } catch (const std::exception& error) {
        SPDLOG_ERROR("Vita audio thread creation failed: {}", error.what());
        DoClose();
        return false;
    }

    SPDLOG_INFO("Vita native audio initialized: stereo, {} -> {} Hz, {} frame blocks", GetSampleRate(),
                gVitaResampler.outputRate, OutputFrames);
    return true;
#else
    if (SDL_Init(SDL_INIT_AUDIO) != 0) {
        SPDLOG_ERROR("SDL init error: {}", SDL_GetError());
        return false;
    }

    // Always open with the correct number of output channels
    mNumChannels = this->GetNumOutputChannels();

    SDL_AudioSpec want, have;
    SDL_zero(want);
    want.freq = this->GetSampleRate();
    want.format = AUDIO_S16SYS;
    want.channels = mNumChannels;
    want.samples = this->GetSampleLength();
    want.callback = NULL;

    mDevice = SDL_OpenAudioDevice(NULL, 0, &want, &have, 0);
    if (mDevice == 0) {
        SPDLOG_ERROR("SDL_OpenAudio error: {}", SDL_GetError());
        return false;
    }

    SPDLOG_INFO("SDL Audio initialized: {} channels, {} Hz", mNumChannels, this->GetSampleRate());

    SDL_PauseAudioDevice(mDevice, 0);
    return true;
#endif
}

int SDLAudioPlayer::Buffered() {
#ifdef __vita__
    int port = -1;
    size_t queued = 0;
    {
        std::lock_guard<std::mutex> lock(mQueueMutex);
        port = mPort;
        queued = mQueuedFrames;
    }
    const int hardwareFrames = port >= 0 ? sceAudioOutGetRestSample(port) : 0;
    const size_t outputFrames = queued + static_cast<size_t>(std::max(hardwareFrames, 0));
    const size_t sourceFrames = outputFrames * static_cast<size_t>(GetSampleRate()) /
                                static_cast<size_t>(gVitaResampler.outputRate);
    return static_cast<int>(std::min(sourceFrames, static_cast<size_t>(std::numeric_limits<int>::max())));
#else
    return SDL_GetQueuedAudioSize(mDevice) / (sizeof(int16_t) * mNumChannels);
#endif
}

void SDLAudioPlayer::DoPlay(const uint8_t* buf, size_t len) {
#ifdef __vita__
    if (buf == nullptr || len < sizeof(int16_t) * mNumChannels) {
        return;
    }

    const int16_t* input = reinterpret_cast<const int16_t*>(buf);
    const size_t inputFrames = len / (sizeof(int16_t) * mNumChannels);

    std::unique_lock<std::mutex> lock(mQueueMutex);
    if (!mRunning || mQueue.empty()) {
        return;
    }

    gVitaResampler.scratch.clear();
    size_t inputFrame = 0;
    if (!gVitaResampler.havePreviousFrame) {
        gVitaResampler.previousFrame[0] = input[0];
        gVitaResampler.previousFrame[1] = input[1];
        gVitaResampler.havePreviousFrame = true;
        inputFrame = 1;
    }

    const uint32_t sourceRate = static_cast<uint32_t>(GetSampleRate());
    const uint32_t outputRate = static_cast<uint32_t>(gVitaResampler.outputRate);
    for (; inputFrame < inputFrames; ++inputFrame) {
        const int16_t* current = input + inputFrame * mNumChannels;
        while (gVitaResampler.phase < outputRate) {
            const int32_t previousWeight = static_cast<int32_t>(outputRate - gVitaResampler.phase);
            const int32_t currentWeight = static_cast<int32_t>(gVitaResampler.phase);
            for (int channel = 0; channel < mNumChannels; ++channel) {
                const int32_t weighted = static_cast<int32_t>(gVitaResampler.previousFrame[channel]) * previousWeight +
                                         static_cast<int32_t>(current[channel]) * currentWeight;
                const int32_t sample = outputRate == static_cast<uint32_t>(kPreferredOutputRate)
                                           ? weighted / kPreferredOutputRate
                                           : weighted / kFallbackOutputRate;
                gVitaResampler.scratch.push_back(static_cast<int16_t>(sample));
            }
            gVitaResampler.phase += sourceRate;
        }
        gVitaResampler.phase -= outputRate;
        gVitaResampler.previousFrame[0] = current[0];
        gVitaResampler.previousFrame[1] = current[1];
    }

    const int16_t* output = gVitaResampler.scratch.data();
    size_t outputFrames = gVitaResampler.scratch.size() / mNumChannels;
    if (outputFrames > QueueFrames) {
        output += (outputFrames - QueueFrames) * mNumChannels;
        outputFrames = QueueFrames;
    }

    if (outputFrames > QueueFrames - mQueuedFrames) {
        const size_t discarded = outputFrames - (QueueFrames - mQueuedFrames);
        mReadFrame = (mReadFrame + discarded) % QueueFrames;
        mQueuedFrames -= discarded;
    }

    const size_t firstFrames = std::min(outputFrames, QueueFrames - mWriteFrame);
    std::memcpy(&mQueue[mWriteFrame * mNumChannels], output,
                firstFrames * mNumChannels * sizeof(int16_t));
    const size_t secondFrames = outputFrames - firstFrames;
    if (secondFrames > 0) {
        std::memcpy(mQueue.data(), output + firstFrames * mNumChannels,
                    secondFrames * mNumChannels * sizeof(int16_t));
    }
    mWriteFrame = (mWriteFrame + outputFrames) % QueueFrames;
    mQueuedFrames += outputFrames;
    lock.unlock();
    mQueueReady.notify_one();
#else
    if (Buffered() < 6000) {
        // Don't fill the audio buffer too much in case this happens
        SDL_QueueAudio(mDevice, buf, len);
    }
#endif
}

#ifdef __vita__
void SDLAudioPlayer::OutputLoop() {
    alignas(64) std::array<int16_t, OutputFrames * 2> output{};
    bool started = false;

    for (;;) {
        std::unique_lock<std::mutex> lock(mQueueMutex);
        const size_t requiredFrames = started ? OutputFrames : OutputFrames * 3;
        mQueueReady.wait(lock, [this, requiredFrames] { return !mRunning || mQueuedFrames >= requiredFrames; });
        if (!mRunning) {
            break;
        }

        const size_t firstFrames = std::min(OutputFrames, QueueFrames - mReadFrame);
        std::memcpy(output.data(), &mQueue[mReadFrame * mNumChannels],
                    firstFrames * mNumChannels * sizeof(int16_t));
        const size_t secondFrames = OutputFrames - firstFrames;
        if (secondFrames > 0) {
            std::memcpy(output.data() + firstFrames * mNumChannels, mQueue.data(),
                        secondFrames * mNumChannels * sizeof(int16_t));
        }
        mReadFrame = (mReadFrame + OutputFrames) % QueueFrames;
        mQueuedFrames -= OutputFrames;
        lock.unlock();

        started = true;
        const int result = sceAudioOutOutput(mPort, output.data());
        if (result < 0) {
            SPDLOG_ERROR("sceAudioOutOutput failed: {:#x}", static_cast<uint32_t>(result));
            std::lock_guard<std::mutex> stopLock(mQueueMutex);
            mRunning = false;
            break;
        }
    }
}
#endif
} // namespace Ship
