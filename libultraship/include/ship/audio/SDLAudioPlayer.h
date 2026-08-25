#pragma once
#include "AudioPlayer.h"
#ifdef __vita__
#include <condition_variable>
#include <mutex>
#include <thread>
#include <vector>
#else
#include <SDL2/SDL.h>
#endif

namespace Ship {
class SDLAudioPlayer final : public AudioPlayer {
  public:
    SDLAudioPlayer(AudioSettings settings) : AudioPlayer(settings) {
    }
    ~SDLAudioPlayer();

    int Buffered() override;

  protected:
    bool DoInit() override;
    void DoClose() override;
    void DoPlay(const uint8_t* buf, size_t len) override;

  private:
#ifdef __vita__
    static constexpr size_t OutputFrames = 512;
    static constexpr size_t StartFrames = OutputFrames * 2;
    static constexpr size_t QueueFrames = 8192;

    void OutputLoop();

    int mPort = -1;
    std::thread mOutputThread;
    std::mutex mQueueMutex;
    std::condition_variable mQueueReady;
    std::vector<int16_t> mQueue;
    size_t mReadFrame = 0;
    size_t mWriteFrame = 0;
    size_t mQueuedFrames = 0;
    bool mRunning = false;
#else
    SDL_AudioDeviceID mDevice = 0;
#endif
    int32_t mNumChannels = 2;
};
} // namespace Ship
