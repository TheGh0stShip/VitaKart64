#include "VitaLoadingScreen.h"

#ifdef __vita__

#include <algorithm>
#include <atomic>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <malloc.h>

#include <png.h>
#include <vitaGL.h>
#include <vitasdk.h>

namespace VitaLoadingScreen {
namespace {

constexpr int ScreenWidth = 960;
constexpr int ScreenHeight = 544;
constexpr int ScreenStride = 960;
constexpr size_t ScreenPixels = static_cast<size_t>(ScreenStride) * ScreenHeight;
constexpr size_t ScreenBytes = ScreenPixels * sizeof(uint32_t);
constexpr uint64_t PresentIntervalUs = 100000;

uint32_t* sBase = nullptr;
uint32_t* sFrames[2] = { nullptr, nullptr };
std::atomic<uint32_t*> sPublished{ nullptr };
std::atomic<bool> sActive{ false };
int sWriteIndex = 0;
bool sGraphicsReady = false;
uint64_t sStartedAt = 0;
uint64_t sLastPresentAt = 0;
uint32_t sProgressPermille = 0;
char sStage[96] = "STARTING";
char sDetail[128] = "PREPARING VITA KART 64";

constexpr uint32_t Rgba(uint8_t r, uint8_t g, uint8_t b, uint8_t a = 255) {
    return static_cast<uint32_t>(r) | (static_cast<uint32_t>(g) << 8) | (static_cast<uint32_t>(b) << 16) |
           (static_cast<uint32_t>(a) << 24);
}

void FillFallbackArtwork(uint32_t* pixels) {
    for (int y = 0; y < ScreenHeight; y++) {
        for (int x = 0; x < ScreenWidth; x++) {
            const int glowX = std::max(0, 420 - std::abs(x - ScreenWidth / 2));
            const int glowY = std::max(0, 260 - std::abs(y - 210));
            const uint8_t blue = static_cast<uint8_t>(18 + (glowX * glowY) / 15000);
            const uint8_t green = static_cast<uint8_t>(7 + (glowX * glowY) / 30000);
            pixels[y * ScreenStride + x] = Rgba(2, green, blue);
        }
    }
}

bool LoadArtwork(uint32_t* pixels) {
    png_image image{};
    image.version = PNG_IMAGE_VERSION;
    if (!png_image_begin_read_from_file(&image, "app0:/loading.png")) {
        return false;
    }
    if (image.width != ScreenWidth || image.height != ScreenHeight) {
        png_image_free(&image);
        return false;
    }

    image.format = PNG_FORMAT_RGBA;
    auto* rgba = static_cast<uint8_t*>(malloc(PNG_IMAGE_SIZE(image)));
    if (rgba == nullptr) {
        png_image_free(&image);
        return false;
    }
    const bool loaded = png_image_finish_read(&image, nullptr, rgba, 0, nullptr) != 0;
    if (loaded) {
        for (size_t i = 0; i < static_cast<size_t>(ScreenWidth) * ScreenHeight; i++) {
            pixels[i] = Rgba(rgba[i * 4], rgba[i * 4 + 1], rgba[i * 4 + 2], rgba[i * 4 + 3]);
        }
    }
    free(rgba);
    png_image_free(&image);
    return loaded;
}

void DrawRect(uint32_t* pixels, int x, int y, int width, int height, uint32_t color) {
    const int x0 = std::clamp(x, 0, ScreenWidth);
    const int y0 = std::clamp(y, 0, ScreenHeight);
    const int x1 = std::clamp(x + width, 0, ScreenWidth);
    const int y1 = std::clamp(y + height, 0, ScreenHeight);
    for (int py = y0; py < y1; py++) {
        uint32_t* row = pixels + py * ScreenStride;
        for (int px = x0; px < x1; px++) {
            row[px] = color;
        }
    }
}

void BlendRect(uint32_t* pixels, int x, int y, int width, int height, uint32_t color, uint8_t alpha) {
    const int x0 = std::clamp(x, 0, ScreenWidth);
    const int y0 = std::clamp(y, 0, ScreenHeight);
    const int x1 = std::clamp(x + width, 0, ScreenWidth);
    const int y1 = std::clamp(y + height, 0, ScreenHeight);
    const int invAlpha = 255 - alpha;
    const int sr = color & 0xFF;
    const int sg = (color >> 8) & 0xFF;
    const int sb = (color >> 16) & 0xFF;
    for (int py = y0; py < y1; py++) {
        uint32_t* row = pixels + py * ScreenStride;
        for (int px = x0; px < x1; px++) {
            const uint32_t dst = row[px];
            const int r = ((dst & 0xFF) * invAlpha + sr * alpha) / 255;
            const int g = (((dst >> 8) & 0xFF) * invAlpha + sg * alpha) / 255;
            const int b = (((dst >> 16) & 0xFF) * invAlpha + sb * alpha) / 255;
            row[px] = Rgba(static_cast<uint8_t>(r), static_cast<uint8_t>(g), static_cast<uint8_t>(b));
        }
    }
}

#define GLYPH(a, b, c, d, e, f, g)                                                                                 \
    (static_cast<uint64_t>(a) | (static_cast<uint64_t>(b) << 5) | (static_cast<uint64_t>(c) << 10) |               \
     (static_cast<uint64_t>(d) << 15) | (static_cast<uint64_t>(e) << 20) | (static_cast<uint64_t>(f) << 25) |      \
     (static_cast<uint64_t>(g) << 30))

uint64_t Glyph(char c) {
    if (c >= 'a' && c <= 'z') {
        c -= 'a' - 'A';
    }
    switch (c) {
        case 'A': return GLYPH(14, 17, 17, 31, 17, 17, 17);
        case 'B': return GLYPH(30, 17, 17, 30, 17, 17, 30);
        case 'C': return GLYPH(15, 16, 16, 16, 16, 16, 15);
        case 'D': return GLYPH(30, 17, 17, 17, 17, 17, 30);
        case 'E': return GLYPH(31, 16, 16, 30, 16, 16, 31);
        case 'F': return GLYPH(31, 16, 16, 30, 16, 16, 16);
        case 'G': return GLYPH(15, 16, 16, 23, 17, 17, 14);
        case 'H': return GLYPH(17, 17, 17, 31, 17, 17, 17);
        case 'I': return GLYPH(31, 4, 4, 4, 4, 4, 31);
        case 'J': return GLYPH(7, 2, 2, 2, 18, 18, 12);
        case 'K': return GLYPH(17, 18, 20, 24, 20, 18, 17);
        case 'L': return GLYPH(16, 16, 16, 16, 16, 16, 31);
        case 'M': return GLYPH(17, 27, 21, 21, 17, 17, 17);
        case 'N': return GLYPH(17, 25, 21, 19, 17, 17, 17);
        case 'O': return GLYPH(14, 17, 17, 17, 17, 17, 14);
        case 'P': return GLYPH(30, 17, 17, 30, 16, 16, 16);
        case 'Q': return GLYPH(14, 17, 17, 17, 21, 18, 13);
        case 'R': return GLYPH(30, 17, 17, 30, 20, 18, 17);
        case 'S': return GLYPH(15, 16, 16, 14, 1, 1, 30);
        case 'T': return GLYPH(31, 4, 4, 4, 4, 4, 4);
        case 'U': return GLYPH(17, 17, 17, 17, 17, 17, 14);
        case 'V': return GLYPH(17, 17, 17, 17, 17, 10, 4);
        case 'W': return GLYPH(17, 17, 17, 21, 21, 27, 17);
        case 'X': return GLYPH(17, 17, 10, 4, 10, 17, 17);
        case 'Y': return GLYPH(17, 17, 10, 4, 4, 4, 4);
        case 'Z': return GLYPH(31, 1, 2, 4, 8, 16, 31);
        case '0': return GLYPH(14, 17, 19, 21, 25, 17, 14);
        case '1': return GLYPH(4, 12, 4, 4, 4, 4, 14);
        case '2': return GLYPH(14, 17, 1, 2, 4, 8, 31);
        case '3': return GLYPH(30, 1, 1, 14, 1, 1, 30);
        case '4': return GLYPH(2, 6, 10, 18, 31, 2, 2);
        case '5': return GLYPH(31, 16, 16, 30, 1, 1, 30);
        case '6': return GLYPH(14, 16, 16, 30, 17, 17, 14);
        case '7': return GLYPH(31, 1, 2, 4, 8, 8, 8);
        case '8': return GLYPH(14, 17, 17, 14, 17, 17, 14);
        case '9': return GLYPH(14, 17, 17, 15, 1, 1, 14);
        case ':': return GLYPH(0, 4, 4, 0, 4, 4, 0);
        case '.': return GLYPH(0, 0, 0, 0, 0, 6, 6);
        case '-': return GLYPH(0, 0, 0, 31, 0, 0, 0);
        case '/': return GLYPH(1, 2, 2, 4, 8, 8, 16);
        case '%': return GLYPH(25, 26, 2, 4, 8, 11, 19);
        case '(': return GLYPH(2, 4, 8, 8, 8, 4, 2);
        case ')': return GLYPH(8, 4, 2, 2, 2, 4, 8);
        case '+': return GLYPH(0, 4, 4, 31, 4, 4, 0);
        default: return 0;
    }
}

#undef GLYPH

int TextWidth(const char* text, int scale) {
    const int count = static_cast<int>(strlen(text));
    return count == 0 ? 0 : count * 6 * scale - scale;
}

void DrawText(uint32_t* pixels, int x, int y, const char* text, int scale, uint32_t color) {
    for (const char* cursor = text; *cursor != '\0'; cursor++) {
        const uint64_t glyph = Glyph(*cursor);
        for (int row = 0; row < 7; row++) {
            const uint8_t bits = static_cast<uint8_t>((glyph >> (row * 5)) & 31);
            for (int column = 0; column < 5; column++) {
                if ((bits & (1 << (4 - column))) != 0) {
                    DrawRect(pixels, x + column * scale, y + row * scale, scale, scale, color);
                }
            }
        }
        x += 6 * scale;
    }
}

void DrawCenteredText(uint32_t* pixels, int y, const char* text, int scale, uint32_t color) {
    DrawText(pixels, (ScreenWidth - TextWidth(text, scale)) / 2, y, text, scale, color);
}

void CopyTruncated(char* output, size_t outputSize, const char* text) {
    if (outputSize == 0) {
        return;
    }
    snprintf(output, outputSize, "%s", text == nullptr ? "" : text);
}

void EllipsizeToWidth(char* text, size_t textSize, int scale, int maxWidth) {
    if (textSize == 0) {
        return;
    }
    size_t length = strlen(text);
    if (TextWidth(text, scale) <= maxWidth) {
        return;
    }
    while (length > 3 && TextWidth(text, scale) > maxWidth) {
        text[--length] = '\0';
    }
    if (length > 3) {
        text[length - 3] = '.';
        text[length - 2] = '.';
        text[length - 1] = '.';
    }
}

void DrawCenteredWrappedText(uint32_t* pixels, int y, const char* text, int scale, uint32_t color, int maxWidth) {
    char first[128];
    CopyTruncated(first, sizeof(first), text);
    if (TextWidth(first, scale) <= maxWidth) {
        DrawCenteredText(pixels, y, first, scale, color);
        return;
    }

    const int maxChars = std::max(1, maxWidth / std::max(1, 6 * scale));
    int split = std::min(static_cast<int>(strlen(first)), maxChars);
    for (int i = split; i > 0; i--) {
        if (first[i] == ' ') {
            split = i;
            break;
        }
    }

    char second[128];
    CopyTruncated(second, sizeof(second), first + split);
    first[split] = '\0';
    while (second[0] == ' ') {
        memmove(second, second + 1, strlen(second + 1) + 1);
    }

    EllipsizeToWidth(first, sizeof(first), scale, maxWidth);
    EllipsizeToWidth(second, sizeof(second), scale, maxWidth);
    DrawCenteredText(pixels, y, first, scale, color);
    DrawCenteredText(pixels, y + 14 * scale, second, scale, color);
}

void DrawN64Badge(uint32_t* pixels) {
    constexpr int badgeX = 360;
    constexpr int badgeY = 46;
    constexpr int badgeW = 240;
    constexpr int badgeH = 150;
    BlendRect(pixels, badgeX, badgeY, badgeW, badgeH, Rgba(0, 8, 20), 112);
    DrawRect(pixels, badgeX + 18, badgeY + 116, badgeW - 36, 3, Rgba(22, 196, 224));
    DrawRect(pixels, badgeX + 18, badgeY + 122, badgeW - 36, 2, Rgba(255, 188, 45));
    DrawRect(pixels, badgeX + 42, badgeY + 24, 18, 82, Rgba(255, 57, 57));
    DrawRect(pixels, badgeX + 62, badgeY + 46, 18, 60, Rgba(69, 205, 84));
    DrawRect(pixels, badgeX + 82, badgeY + 68, 18, 38, Rgba(44, 111, 246));
    DrawText(pixels, badgeX + 118, badgeY + 28, "N64", 7, Rgba(4, 13, 28));
    DrawText(pixels, badgeX + 112, badgeY + 22, "N64", 7, Rgba(246, 249, 255));
    DrawCenteredText(pixels, badgeY + 132, "STATIC RECOMPILATION", 1, Rgba(196, 215, 232));
}

void FormatTime(char* output, size_t outputSize, uint64_t microseconds) {
    const uint64_t seconds = microseconds / 1000000;
    snprintf(output, outputSize, "%02llu:%02llu", static_cast<unsigned long long>(seconds / 60),
             static_cast<unsigned long long>(seconds % 60));
}

void RenderScreen() {
    if (sBase == nullptr || sFrames[0] == nullptr || sFrames[1] == nullptr) {
        return;
    }
    const int nextIndex = 1 - sWriteIndex;
    uint32_t* frame = sFrames[nextIndex];
    memcpy(frame, sBase, ScreenBytes);
    DrawN64Badge(frame);
    BlendRect(frame, 0, 312, ScreenWidth, ScreenHeight - 312, Rgba(0, 5, 16), 210);
    DrawCenteredText(frame, 330, "VITA KART 64", 3, Rgba(242, 246, 255));
    DrawRect(frame, 348, 359, 264, 2, Rgba(22, 196, 224));
    DrawCenteredText(frame, 378, sStage, 2, Rgba(255, 188, 45));
    DrawCenteredWrappedText(frame, 401, sDetail, 1, Rgba(196, 215, 232), 760);

    constexpr int barX = 116;
    constexpr int barY = 428;
    constexpr int barWidth = 728;
    constexpr int barHeight = 16;
    DrawRect(frame, barX, barY, barWidth, barHeight, Rgba(19, 32, 48));
    DrawRect(frame, barX + 2, barY + 2, barWidth - 4, barHeight - 4, Rgba(4, 10, 22));
    const int fillWidth = static_cast<int>((barWidth - 4) * std::min(sProgressPermille, 1000U) / 1000U);
    DrawRect(frame, barX + 2, barY + 2, fillWidth, barHeight - 4, Rgba(22, 196, 224));
    if (fillWidth > 8) {
        DrawRect(frame, barX + fillWidth - 2, barY + 2, 4, barHeight - 4, Rgba(255, 188, 45));
    }
    char percentText[32];
    snprintf(percentText, sizeof(percentText), "%u%%", std::min(sProgressPermille, 1000U) / 10);
    DrawCenteredText(frame, barY + 22, percentText, 2, Rgba(255, 188, 45));

    const uint64_t now = sceKernelGetProcessTimeWide();
    const uint64_t elapsed = sStartedAt == 0 ? 0 : now - sStartedAt;
    char elapsedText[64];
    char elapsedValue[16];
    FormatTime(elapsedValue, sizeof(elapsedValue), elapsed);
    snprintf(elapsedText, sizeof(elapsedText), "ELAPSED %s", elapsedValue);
    DrawText(frame, barX, 460, elapsedText, 2, Rgba(242, 246, 255));

    char remainingText[64] = "EST. REMAINING CALCULATING";
    if (sProgressPermille >= 30 && sProgressPermille < 1000) {
        const uint64_t remaining = elapsed * (1000 - sProgressPermille) / sProgressPermille;
        char remainingValue[16];
        FormatTime(remainingValue, sizeof(remainingValue), remaining);
        snprintf(remainingText, sizeof(remainingText), "EST. REMAINING %s", remainingValue);
    } else if (sProgressPermille >= 1000) {
        snprintf(remainingText, sizeof(remainingText), "EST. REMAINING 00:00");
    }
    DrawText(frame, ScreenWidth - barX - TextWidth(remainingText, 2), 460, remainingText, 2, Rgba(242, 246, 255));
    DrawCenteredText(frame, 498, "CACHE STATUS PACKAGED AND VITA LOCAL MANIFESTS", 1, Rgba(94, 224, 177));
    DrawCenteredText(frame, 516, "FIRST START MAY BUILD DATA. FUTURE STARTS REUSE IT.", 1, Rgba(130, 150, 170));
    sWriteIndex = nextIndex;
    sPublished.store(frame, std::memory_order_release);
}

void DisplayCallback(void* framebuffer) {
    if (!sActive.load(std::memory_order_acquire)) {
        return;
    }
    uint32_t* source = sPublished.load(std::memory_order_acquire);
    if (source != nullptr && framebuffer != nullptr) {
        sceClibMemcpy(framebuffer, source, ScreenBytes);
    }
}

void PresentInternal(bool force) {
    if (!sGraphicsReady || !sActive.load(std::memory_order_acquire)) {
        return;
    }
    const uint64_t now = sceKernelGetProcessTimeWide();
    if (!force && now - sLastPresentAt < PresentIntervalUs) {
        return;
    }
    sLastPresentAt = now;
    vglSwapBuffers(GL_FALSE);
}

} // namespace

void Begin() {
    if (sActive.load(std::memory_order_acquire)) {
        return;
    }
    sBase = static_cast<uint32_t*>(memalign(64, ScreenBytes));
    sFrames[0] = static_cast<uint32_t*>(memalign(64, ScreenBytes));
    sFrames[1] = static_cast<uint32_t*>(memalign(64, ScreenBytes));
    if (sBase == nullptr || sFrames[0] == nullptr || sFrames[1] == nullptr) {
        free(sBase);
        free(sFrames[0]);
        free(sFrames[1]);
        sBase = nullptr;
        sFrames[0] = nullptr;
        sFrames[1] = nullptr;
        return;
    }
    if (!LoadArtwork(sBase)) {
        FillFallbackArtwork(sBase);
    }
    sStartedAt = sceKernelGetProcessTimeWide();
    sProgressPermille = 30;
    snprintf(sStage, sizeof(sStage), "INITIALIZING GRAPHICS DRIVER");
    snprintf(sDetail, sizeof(sDetail), "PREPARING GPU AND PERSISTENT CACHE");
    sActive.store(true, std::memory_order_release);
    RenderScreen();
    vglSetDisplayCallback(DisplayCallback);
}

void GraphicsReady() {
    sGraphicsReady = true;
    SetStage("GRAPHICS DRIVER READY", "CREATING RENDER TARGETS AND USER INTERFACE", 260);
}

void SetStage(const char* stage, const char* detail, uint32_t progressPermille) {
    if (!sActive.load(std::memory_order_acquire)) {
        return;
    }
    snprintf(sStage, sizeof(sStage), "%s", stage == nullptr ? "LOADING" : stage);
    snprintf(sDetail, sizeof(sDetail), "%s", detail == nullptr ? "" : detail);
    sProgressPermille = std::min(progressPermille, 1000U);
    RenderScreen();
    Present();
}

void SetProgress(const char* stage, const char* detail, uint32_t current, uint32_t total,
                 uint32_t startPermille, uint32_t endPermille) {
    const uint32_t safeTotal = std::max(total, 1U);
    const uint32_t clampedCurrent = std::min(current, safeTotal);
    const uint32_t progress = startPermille +
                              static_cast<uint32_t>((static_cast<uint64_t>(endPermille - startPermille) *
                                                     clampedCurrent) /
                                                    safeTotal);
    char progressDetail[128];
    snprintf(progressDetail, sizeof(progressDetail), "%s  %u / %u", detail == nullptr ? "ITEM" : detail,
             clampedCurrent, safeTotal);
    SetStage(stage, progressDetail, progress);
}

void Present() {
    PresentInternal(false);
}

void PrefetchFile(const char* path, const char* label, uint32_t startPermille, uint32_t endPermille) {
    SceUID file = sceIoOpen(path, SCE_O_RDONLY, 0);
    if (file < 0) {
        return;
    }
    const SceOff size = sceIoLseek(file, 0, SCE_SEEK_END);
    sceIoLseek(file, 0, SCE_SEEK_SET);
    if (size <= 0) {
        sceIoClose(file);
        return;
    }
    constexpr size_t BufferSize = 256 * 1024;
    auto* buffer = static_cast<uint8_t*>(memalign(64, BufferSize));
    if (buffer == nullptr) {
        sceIoClose(file);
        return;
    }
    SceOff readTotal = 0;
    while (readTotal < size) {
        const int bytesRead = sceIoRead(file, buffer, BufferSize);
        if (bytesRead <= 0) {
            break;
        }
        readTotal += bytesRead;
        SetProgress("PRECACHING GAME ASSETS", label, static_cast<uint32_t>(readTotal / 1024),
                    static_cast<uint32_t>(size / 1024), startPermille, endPermille);
    }
    free(buffer);
    sceIoClose(file);
}

void End() {
    if (!sActive.load(std::memory_order_acquire)) {
        return;
    }
    SetStage("READY", "STARTING VITA KART 64", 1000);
    PresentInternal(true);
    sceGxmDisplayQueueFinish();
    vglSetDisplayCallback(nullptr);
    sActive.store(false, std::memory_order_release);
    sPublished.store(nullptr, std::memory_order_release);
    free(sBase);
    free(sFrames[0]);
    free(sFrames[1]);
    sBase = nullptr;
    sFrames[0] = nullptr;
    sFrames[1] = nullptr;
}

} // namespace VitaLoadingScreen

#else

namespace VitaLoadingScreen {
void Begin() {}
void GraphicsReady() {}
void SetStage(const char*, const char*, uint32_t) {}
void SetProgress(const char*, const char*, uint32_t, uint32_t, uint32_t, uint32_t) {}
void Present() {}
void PrefetchFile(const char*, const char*, uint32_t, uint32_t) {}
void End() {}
} // namespace VitaLoadingScreen

#endif
