#pragma once

#include <stdint.h>

namespace VitaLoadingScreen {

void Begin();
void GraphicsReady();
void SetStage(const char* stage, const char* detail, uint32_t progressPermille);
void SetProgress(const char* stage, const char* detail, uint32_t current, uint32_t total,
                 uint32_t startPermille, uint32_t endPermille);
void Present();
void PrefetchFile(const char* path, const char* label, uint32_t startPermille, uint32_t endPermille);
void End();

} // namespace VitaLoadingScreen
