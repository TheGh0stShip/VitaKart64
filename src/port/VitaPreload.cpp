#include "VitaPreload.h"

#ifdef __vita__

#include "Engine.h"
#include "VitaLoadingScreen.h"

#include <fast/resource/type/Texture.h>
#include <ship/Context.h>
#include <ship/resource/Resource.h>
#include <ship/resource/ResourceManager.h>

#include <algorithm>
#include <array>
#include <cstdlib>
#include <cstdio>
#include <memory>
#include <string>
#include <unordered_map>
#include <unordered_set>
#include <vector>

#include <vitasdk.h>

#ifndef VITAKART_TEXTURE_PAIR_LIMIT
#define VITAKART_TEXTURE_PAIR_LIMIT 0
#endif

namespace {

constexpr uint32_t kVitaTexturePreloadSlots = 24576;

std::vector<std::shared_ptr<Ship::IResource>> sResidentResources;

struct TextureEntry {
    std::string path;
    std::shared_ptr<Fast::Texture> texture;
};

struct PalettedWarmupStats {
    uint32_t manifestPairsAttempted = 0;
    uint32_t manifestPairsWarmed = 0;
    uint32_t manifestPairsDuplicate = 0;
    uint32_t heuristicPairsAttempted = 0;
    uint32_t heuristicPairsWarmed = 0;
    uint32_t heuristicPairsDuplicate = 0;
};

constexpr std::array<const char*, 25> kRuntimeGroups = {
    "textures/karts/*",
    "textures/other_textures/*",
    "textures/player_selection/*",
    "textures/texture_tkmk00/*",
    "textures/tracks/*",
    "textures/texture_data_2/*",
    "textures/common_data/*",
    "textures/boo_frames/*",
    "textures/ceremony_data/*",
    "textures/startup_logo/*",
    "textures/some_data/*",
    "models/tracks/*",
    "models/startup_logo/*",
    "models/common_data/*",
    "models/ceremony_data/*",
    "models/data_800E8700/*",
    "models/data_segment2/*",
    "sound/samples/*",
    "sound/sequences/*",
    "sound/banks/*",
    "sound/root/*",
    "other/tracks/*",
    "other/common_data/*",
    "other/ceremony_data/*",
    "other/startup_logo/*",
};

constexpr std::array<const char*, 2> kTexturePairManifests = {
    "app0:/texture-pairs.manifest",
    "ux0:data/vitakart64/texture-pairs.manifest",
};

static bool StartsWith(const std::string& value, const char* prefix) {
    return value.rfind(prefix, 0) == 0;
}

static bool IsSpace(char c) {
    return c == ' ' || c == '\t' || c == '\r' || c == '\n';
}

static bool NextToken(const std::string& line, size_t& offset, std::string& token) {
    while (offset < line.size() && IsSpace(line[offset])) {
        offset++;
    }
    if (offset >= line.size()) {
        return false;
    }

    const size_t start = offset;
    while (offset < line.size() && !IsSpace(line[offset])) {
        offset++;
    }
    token = line.substr(start, offset - start);
    return true;
}

static bool TexturePairWarmupLimitReached(uint32_t warmed) {
#if VITAKART_TEXTURE_PAIR_LIMIT > 0
    return warmed >= VITAKART_TEXTURE_PAIR_LIMIT;
#else
    return false;
#endif
}

static std::string MakePairKey(const std::string& texturePath, const std::string& palettePath, uint8_t paletteIndex) {
    std::string key = texturePath;
    key.push_back('\n');
    key += palettePath;
    key.push_back('\n');
    key += std::to_string(static_cast<unsigned>(paletteIndex));
    return key;
}

static std::string DirectoryName(const std::string& path) {
    const size_t slash = path.find_last_of('/');
    return slash == std::string::npos ? std::string() : path.substr(0, slash + 1);
}

static std::string BaseName(const std::string& path) {
    const size_t slash = path.find_last_of('/');
    return slash == std::string::npos ? path : path.substr(slash + 1);
}

static bool IsCiTexture(const std::shared_ptr<Fast::Texture>& texture) {
    return texture != nullptr &&
           (texture->Type == Fast::TextureType::Palette4bpp || texture->Type == Fast::TextureType::Palette8bpp);
}

static bool IsPaletteResourcePath(const std::string& path) {
    const std::string base = BaseName(path);
    return base.find("tlut") != std::string::npos || base.find("TLUT") != std::string::npos;
}

static bool FileExists(const char* path) {
    FILE* file = std::fopen(path, "r");
    if (file == nullptr) {
        return false;
    }

    std::fclose(file);
    return true;
}

static int RuntimePreloadPriority(const std::string& path) {
    if (StartsWith(path, "textures/common_data/") || StartsWith(path, "textures/player_selection/") ||
        StartsWith(path, "textures/startup_logo/") || StartsWith(path, "textures/texture_tkmk00/")) {
        return 0;
    }

    if (StartsWith(path, "sound/")) {
        return 1;
    }

    if (StartsWith(path, "textures/ceremony_data/") || StartsWith(path, "models/ceremony_data/") ||
        StartsWith(path, "other/ceremony_data/")) {
        return 2;
    }

    if (StartsWith(path, "models/common_data/") || StartsWith(path, "models/startup_logo/") ||
        StartsWith(path, "other/common_data/") || StartsWith(path, "other/startup_logo/")) {
        return 3;
    }

    if (StartsWith(path, "textures/karts/")) {
        return 4;
    }

    if (StartsWith(path, "textures/tracks/") || StartsWith(path, "models/tracks/") ||
        StartsWith(path, "other/tracks/")) {
        return 5;
    }

    return 6;
}

static bool ParseTexturePairManifestLine(const char* rawLine, std::string& texturePath, std::string& palettePath,
                                         uint8_t& paletteIndex) {
    std::string line = rawLine;
    const size_t comment = line.find('#');
    if (comment != std::string::npos) {
        line.resize(comment);
    }

    size_t offset = 0;
    std::string indexToken;
    if (!NextToken(line, offset, texturePath) || !NextToken(line, offset, palettePath)) {
        return false;
    }

    paletteIndex = 0;
    if (NextToken(line, offset, indexToken)) {
        paletteIndex = static_cast<uint8_t>(std::strtoul(indexToken.c_str(), nullptr, 0) & 0xF);
    }
    return true;
}

static std::shared_ptr<Fast::Texture>
GetTextureForPath(std::unordered_map<std::string, std::shared_ptr<Fast::Texture>>& texturesByPath,
                  const std::shared_ptr<Ship::ResourceManager>& resourceManager, const std::string& path) {
    const auto existing = texturesByPath.find(path);
    if (existing != texturesByPath.end()) {
        return existing->second;
    }

    if (resourceManager == nullptr) {
        return nullptr;
    }

    const auto resource = resourceManager->LoadResource(path);
    const auto texture = std::dynamic_pointer_cast<Fast::Texture>(resource);
    if (texture != nullptr) {
        sResidentResources.push_back(resource);
        texturesByPath.emplace(path, texture);
    }
    return texture;
}

static std::string TrimVariantSuffix(const std::string& suffix) {
    const size_t slash = suffix.find_last_of('_');
    if (slash == std::string::npos || slash + 1 >= suffix.size()) {
        return suffix;
    }

    const std::string tail = suffix.substr(slash + 1);
    bool numeric = true;
    for (char c : tail) {
        if (c < '0' || c > '9') {
            numeric = false;
            break;
        }
    }

    const bool playerSuffix = tail.size() == 2 && tail[0] >= '1' && tail[0] <= '4' && tail[1] == 'p';
    return numeric || playerSuffix ? suffix.substr(0, slash) : suffix;
}

static std::shared_ptr<Fast::Texture>
FindMatchingPalette(const std::unordered_map<std::string, std::shared_ptr<Fast::Texture>>& texturesByPath,
                    const std::string& texturePath) {
    const std::string dir = DirectoryName(texturePath);
    const std::string base = BaseName(texturePath);
    const char* tlutPrefix = nullptr;
    std::string suffix;

    if (StartsWith(base, "common_texture_")) {
        tlutPrefix = "common_tlut_";
        suffix = base.substr(sizeof("common_texture_") - 1);
    } else if (StartsWith(base, "texture_")) {
        tlutPrefix = "tlut_";
        suffix = base.substr(sizeof("texture_") - 1);
    } else {
        return nullptr;
    }

    while (!suffix.empty()) {
        const auto it = texturesByPath.find(dir + tlutPrefix + suffix);
        if (it != texturesByPath.end()) {
            return it->second;
        }

        const std::string trimmed = TrimVariantSuffix(suffix);
        if (trimmed == suffix) {
            break;
        }
        suffix = trimmed;
    }

    if (base == "common_texture_portrait_question_mark") {
        const auto it = texturesByPath.find(dir + "common_tlut_portrait_bomb_kart_and_question_mark");
        if (it != texturesByPath.end()) {
            return it->second;
        }
    }

    return nullptr;
}

static uint32_t WarmPalettedTextureManifests(
    Fast::Interpreter* interpreter, const std::shared_ptr<Ship::ResourceManager>& resourceManager,
    std::unordered_map<std::string, std::shared_ptr<Fast::Texture>>& texturesByPath,
    std::unordered_set<std::string>& attemptedPairs, PalettedWarmupStats& stats) {
    uint32_t warmed = 0;
    uint32_t attempted = 0;
    char detail[160];

    for (const char* manifestPath : kTexturePairManifests) {
        FILE* manifest = std::fopen(manifestPath, "r");
        if (manifest == nullptr) {
            continue;
        }

        char line[512];
        while (std::fgets(line, sizeof(line), manifest) != nullptr) {
            std::string texturePath;
            std::string palettePath;
            uint8_t paletteIndex = 0;
            if (!ParseTexturePairManifestLine(line, texturePath, palettePath, paletteIndex)) {
                continue;
            }

            const std::string pairKey = MakePairKey(texturePath, palettePath, paletteIndex);
            if (!attemptedPairs.insert(pairKey).second) {
                stats.manifestPairsDuplicate++;
                continue;
            }

            const auto texture = GetTextureForPath(texturesByPath, resourceManager, texturePath);
            const auto palette = GetTextureForPath(texturesByPath, resourceManager, palettePath);
            if (interpreter->PreloadTextureResourceWithPalette(texture, palette, paletteIndex)) {
                warmed++;
                stats.manifestPairsWarmed++;
            }
            attempted++;
            stats.manifestPairsAttempted++;

            if (TexturePairWarmupLimitReached(warmed)) {
                std::fclose(manifest);
                return warmed;
            }

            if ((attempted & 31U) == 0) {
                std::snprintf(detail, sizeof(detail), "MANIFEST PAIRS %u   GPU TEXTURES %u", attempted, warmed);
                VitaLoadingScreen::SetStage("PRELOADING PALETTED TEXTURES", detail, 998);
            }
        }

        std::fclose(manifest);
    }

    return warmed;
}

static uint32_t WarmPalettedTexturePairs(Fast::Interpreter* interpreter,
                                         const std::shared_ptr<Ship::ResourceManager>& resourceManager,
                                         const std::vector<TextureEntry>& textures, PalettedWarmupStats& stats) {
    std::unordered_map<std::string, std::shared_ptr<Fast::Texture>> texturesByPath;
    texturesByPath.reserve(textures.size() + 4096);
    for (const TextureEntry& entry : textures) {
        texturesByPath.emplace(entry.path, entry.texture);
    }

    std::unordered_set<std::string> attemptedPairs;
    attemptedPairs.reserve((textures.size() * 2) + 4096);

    uint32_t warmed = WarmPalettedTextureManifests(interpreter, resourceManager, texturesByPath, attemptedPairs, stats);
    if (TexturePairWarmupLimitReached(warmed)) {
        return warmed;
    }

    uint32_t paired = 0;
    char detail[160];
    for (size_t i = 0; i < textures.size(); i++) {
        const TextureEntry& entry = textures[i];
        if (!IsCiTexture(entry.texture)) {
            continue;
        }

        const std::shared_ptr<Fast::Texture> palette = FindMatchingPalette(texturesByPath, entry.path);
        if (palette == nullptr) {
            continue;
        }

        const std::string pairKey = MakePairKey(entry.path, palette->GetInitData()->Path, 0);
        if (!attemptedPairs.insert(pairKey).second) {
            stats.heuristicPairsDuplicate++;
            continue;
        }

        paired++;
        stats.heuristicPairsAttempted++;
        if (interpreter->PreloadTextureResourceWithPalette(entry.texture, palette, 0)) {
            warmed++;
            stats.heuristicPairsWarmed++;
            if (TexturePairWarmupLimitReached(warmed)) {
                return warmed;
            }
        }

        if ((paired & 31U) == 0) {
            std::snprintf(detail, sizeof(detail), "CI/TLUT PAIRS %u   GPU TEXTURES %u", paired, warmed);
            VitaLoadingScreen::SetStage("PRELOADING PALETTED TEXTURES", detail, 998);
        }
    }

    if (paired > 0) {
        std::snprintf(detail, sizeof(detail), "CI/TLUT PAIRS %u   GPU TEXTURES %u", paired, warmed);
        VitaLoadingScreen::SetStage("PRELOADING PALETTED TEXTURES", detail, 998);
    }

    return warmed;
}

static void WarmAudioRuntimeTables(uint32_t& warmedBanks, uint32_t& warmedSequences) {
    warmedBanks = 0;
    warmedSequences = 0;
    VitaLoadingScreen::SetStage("PRELOADING AUDIO TABLES", "BANKS SEQUENCES AND SAMPLE REFERENCES", 998);

    for (uint32_t bankId = 0; bankId < 256; bankId++) {
        if (GameEngine_LoadBank(static_cast<uint8_t>(bankId)) != nullptr) {
            warmedBanks++;
        }
    }

    const uint32_t sequenceCount = std::min<uint32_t>(GameEngine_GetSequenceCount(), 256);
    for (uint32_t sequenceId = 0; sequenceId < sequenceCount; sequenceId++) {
        if (GameEngine_LoadSequence(static_cast<uint8_t>(sequenceId)) != nullptr) {
            warmedSequences++;
        }
    }
}

static void EnsureVitaKartDataDir() {
    sceIoMkdir("ux0:data", 0777);
    sceIoMkdir("ux0:data/vitakart64", 0777);
}

static void WritePreloadSummary(uint32_t residentResources, uint32_t textureResources, uint32_t modelResources,
                                uint32_t audioResources, uint32_t otherResources, uint32_t gpuTextures,
                                uint32_t palettedGpuTextures, uint32_t paletteResources, uint32_t deferredTextures,
                                uint32_t reservedTextureSlots,
                                bool preloadReadyMarkerPresentBeforeRun,
                                const PalettedWarmupStats& palettedWarmupStats,
                                const std::array<uint32_t, 7>& preloadPriorityCounts,
                                const std::array<uint64_t, 7>& preloadPriorityTimeUs,
                                const std::array<uint64_t, 7>& preloadPriorityGpuTimeUs,
                                uint32_t audioWarmupBanks, uint32_t audioWarmupSequences,
                                uint64_t resourcePhaseUs, uint64_t palettedPhaseUs, uint64_t audioPhaseUs,
                                uint64_t totalUs) {
    EnsureVitaKartDataDir();
    FILE* summary = std::fopen("ux0:data/vitakart64/preload-summary.txt", "w");
    if (summary == nullptr) {
        return;
    }

    std::fprintf(summary, "preload_skipped=0\n");
    std::fprintf(summary, "preload_skip_reason=completed\n");
    std::fprintf(summary, "preload_ready_marker=ux0:data/vitakart64/preload-ready.marker\n");
    std::fprintf(summary, "preload_ready_marker_present_before_run=%u\n",
                 preloadReadyMarkerPresentBeforeRun ? 1U : 0U);
    std::fprintf(summary, "texture_pair_limit=%u\n", static_cast<unsigned>(VITAKART_TEXTURE_PAIR_LIMIT));
    std::fprintf(summary, "resident_resources=%u\n", residentResources);
    std::fprintf(summary, "texture_resources=%u\n", textureResources);
    std::fprintf(summary, "model_resources=%u\n", modelResources);
    std::fprintf(summary, "audio_resources=%u\n", audioResources);
    std::fprintf(summary, "other_resources=%u\n", otherResources);
    std::fprintf(summary, "gpu_textures=%u\n", gpuTextures);
    std::fprintf(summary, "paletted_gpu_textures=%u\n", palettedGpuTextures);
    std::fprintf(summary, "palette_resources=%u\n", paletteResources);
    std::fprintf(summary, "deferred_textures=%u\n", deferredTextures);
    std::fprintf(summary, "reserved_texture_slots=%u\n", reservedTextureSlots);
    std::fprintf(summary, "paletted_manifest_pairs_attempted=%u\n", palettedWarmupStats.manifestPairsAttempted);
    std::fprintf(summary, "paletted_manifest_pairs_warmed=%u\n", palettedWarmupStats.manifestPairsWarmed);
    std::fprintf(summary, "paletted_manifest_pairs_duplicate=%u\n", palettedWarmupStats.manifestPairsDuplicate);
    std::fprintf(summary, "paletted_heuristic_pairs_attempted=%u\n", palettedWarmupStats.heuristicPairsAttempted);
    std::fprintf(summary, "paletted_heuristic_pairs_warmed=%u\n", palettedWarmupStats.heuristicPairsWarmed);
    std::fprintf(summary, "paletted_heuristic_pairs_duplicate=%u\n", palettedWarmupStats.heuristicPairsDuplicate);
    std::fprintf(summary, "audio_warmup_banks=%u\n", audioWarmupBanks);
    std::fprintf(summary, "audio_warmup_sequences=%u\n", audioWarmupSequences);
    std::fprintf(summary, "preload_priority_common_menu=%u\n", preloadPriorityCounts[0]);
    std::fprintf(summary, "preload_priority_audio=%u\n", preloadPriorityCounts[1]);
    std::fprintf(summary, "preload_priority_ceremony=%u\n", preloadPriorityCounts[2]);
    std::fprintf(summary, "preload_priority_common_models=%u\n", preloadPriorityCounts[3]);
    std::fprintf(summary, "preload_priority_karts=%u\n", preloadPriorityCounts[4]);
    std::fprintf(summary, "preload_priority_tracks=%u\n", preloadPriorityCounts[5]);
    std::fprintf(summary, "preload_priority_other=%u\n", preloadPriorityCounts[6]);
    std::fprintf(summary, "preload_priority_common_menu_us=%llu\n",
                 static_cast<unsigned long long>(preloadPriorityTimeUs[0]));
    std::fprintf(summary, "preload_priority_audio_us=%llu\n",
                 static_cast<unsigned long long>(preloadPriorityTimeUs[1]));
    std::fprintf(summary, "preload_priority_ceremony_us=%llu\n",
                 static_cast<unsigned long long>(preloadPriorityTimeUs[2]));
    std::fprintf(summary, "preload_priority_common_models_us=%llu\n",
                 static_cast<unsigned long long>(preloadPriorityTimeUs[3]));
    std::fprintf(summary, "preload_priority_karts_us=%llu\n",
                 static_cast<unsigned long long>(preloadPriorityTimeUs[4]));
    std::fprintf(summary, "preload_priority_tracks_us=%llu\n",
                 static_cast<unsigned long long>(preloadPriorityTimeUs[5]));
    std::fprintf(summary, "preload_priority_other_us=%llu\n",
                 static_cast<unsigned long long>(preloadPriorityTimeUs[6]));
    std::fprintf(summary, "preload_priority_common_menu_gpu_us=%llu\n",
                 static_cast<unsigned long long>(preloadPriorityGpuTimeUs[0]));
    std::fprintf(summary, "preload_priority_audio_gpu_us=%llu\n",
                 static_cast<unsigned long long>(preloadPriorityGpuTimeUs[1]));
    std::fprintf(summary, "preload_priority_ceremony_gpu_us=%llu\n",
                 static_cast<unsigned long long>(preloadPriorityGpuTimeUs[2]));
    std::fprintf(summary, "preload_priority_common_models_gpu_us=%llu\n",
                 static_cast<unsigned long long>(preloadPriorityGpuTimeUs[3]));
    std::fprintf(summary, "preload_priority_karts_gpu_us=%llu\n",
                 static_cast<unsigned long long>(preloadPriorityGpuTimeUs[4]));
    std::fprintf(summary, "preload_priority_tracks_gpu_us=%llu\n",
                 static_cast<unsigned long long>(preloadPriorityGpuTimeUs[5]));
    std::fprintf(summary, "preload_priority_other_gpu_us=%llu\n",
                 static_cast<unsigned long long>(preloadPriorityGpuTimeUs[6]));
    std::fprintf(summary, "preload_priority_common_menu_ms=%llu\n",
                 static_cast<unsigned long long>(preloadPriorityTimeUs[0] / 1000));
    std::fprintf(summary, "preload_priority_audio_ms=%llu\n",
                 static_cast<unsigned long long>(preloadPriorityTimeUs[1] / 1000));
    std::fprintf(summary, "preload_priority_ceremony_ms=%llu\n",
                 static_cast<unsigned long long>(preloadPriorityTimeUs[2] / 1000));
    std::fprintf(summary, "preload_priority_common_models_ms=%llu\n",
                 static_cast<unsigned long long>(preloadPriorityTimeUs[3] / 1000));
    std::fprintf(summary, "preload_priority_karts_ms=%llu\n",
                 static_cast<unsigned long long>(preloadPriorityTimeUs[4] / 1000));
    std::fprintf(summary, "preload_priority_tracks_ms=%llu\n",
                 static_cast<unsigned long long>(preloadPriorityTimeUs[5] / 1000));
    std::fprintf(summary, "preload_priority_other_ms=%llu\n",
                 static_cast<unsigned long long>(preloadPriorityTimeUs[6] / 1000));
    std::fprintf(summary, "preload_priority_common_menu_gpu_ms=%llu\n",
                 static_cast<unsigned long long>(preloadPriorityGpuTimeUs[0] / 1000));
    std::fprintf(summary, "preload_priority_audio_gpu_ms=%llu\n",
                 static_cast<unsigned long long>(preloadPriorityGpuTimeUs[1] / 1000));
    std::fprintf(summary, "preload_priority_ceremony_gpu_ms=%llu\n",
                 static_cast<unsigned long long>(preloadPriorityGpuTimeUs[2] / 1000));
    std::fprintf(summary, "preload_priority_common_models_gpu_ms=%llu\n",
                 static_cast<unsigned long long>(preloadPriorityGpuTimeUs[3] / 1000));
    std::fprintf(summary, "preload_priority_karts_gpu_ms=%llu\n",
                 static_cast<unsigned long long>(preloadPriorityGpuTimeUs[4] / 1000));
    std::fprintf(summary, "preload_priority_tracks_gpu_ms=%llu\n",
                 static_cast<unsigned long long>(preloadPriorityGpuTimeUs[5] / 1000));
    std::fprintf(summary, "preload_priority_other_gpu_ms=%llu\n",
                 static_cast<unsigned long long>(preloadPriorityGpuTimeUs[6] / 1000));
    std::fprintf(summary, "resource_phase_us=%llu\n", static_cast<unsigned long long>(resourcePhaseUs));
    std::fprintf(summary, "paletted_phase_us=%llu\n", static_cast<unsigned long long>(palettedPhaseUs));
    std::fprintf(summary, "audio_phase_us=%llu\n", static_cast<unsigned long long>(audioPhaseUs));
    std::fprintf(summary, "total_us=%llu\n", static_cast<unsigned long long>(totalUs));
    std::fprintf(summary, "resource_phase_ms=%llu\n", static_cast<unsigned long long>(resourcePhaseUs / 1000));
    std::fprintf(summary, "paletted_phase_ms=%llu\n", static_cast<unsigned long long>(palettedPhaseUs / 1000));
    std::fprintf(summary, "audio_phase_ms=%llu\n", static_cast<unsigned long long>(audioPhaseUs / 1000));
    std::fprintf(summary, "total_ms=%llu\n", static_cast<unsigned long long>(totalUs / 1000));
    std::fclose(summary);
}

static void WritePreloadSkippedSummary(const char* reason, uint32_t residentResources) {
    EnsureVitaKartDataDir();
    FILE* summary = std::fopen("ux0:data/vitakart64/preload-summary.txt", "w");
    if (summary == nullptr) {
        return;
    }

    std::fprintf(summary, "preload_skipped=1\n");
    std::fprintf(summary, "preload_skip_reason=%s\n", reason != nullptr ? reason : "unknown");
    std::fprintf(summary, "preload_ready_marker=\n");
    std::fprintf(summary, "resident_resources=%u\n", residentResources);
    std::fclose(summary);
}

static void WritePreloadReadyMarker(uint32_t residentResources, uint32_t gpuTextures, uint32_t palettedGpuTextures,
                                    uint32_t reservedTextureSlots, const PalettedWarmupStats& palettedWarmupStats,
                                    uint32_t audioWarmupBanks, uint32_t audioWarmupSequences, uint64_t totalUs) {
    EnsureVitaKartDataDir();
    FILE* marker = std::fopen("ux0:data/vitakart64/preload-ready.marker", "w");
    if (marker == nullptr) {
        return;
    }

    std::fprintf(marker, "schema=vitakart64.preload-ready.v1\n");
    std::fprintf(marker, "resident_resources=%u\n", residentResources);
    std::fprintf(marker, "gpu_textures=%u\n", gpuTextures);
    std::fprintf(marker, "paletted_gpu_textures=%u\n", palettedGpuTextures);
    std::fprintf(marker, "paletted_manifest_pairs_attempted=%u\n", palettedWarmupStats.manifestPairsAttempted);
    std::fprintf(marker, "paletted_manifest_pairs_warmed=%u\n", palettedWarmupStats.manifestPairsWarmed);
    std::fprintf(marker, "paletted_manifest_pairs_duplicate=%u\n", palettedWarmupStats.manifestPairsDuplicate);
    std::fprintf(marker, "paletted_heuristic_pairs_attempted=%u\n", palettedWarmupStats.heuristicPairsAttempted);
    std::fprintf(marker, "paletted_heuristic_pairs_warmed=%u\n", palettedWarmupStats.heuristicPairsWarmed);
    std::fprintf(marker, "paletted_heuristic_pairs_duplicate=%u\n", palettedWarmupStats.heuristicPairsDuplicate);
    std::fprintf(marker, "audio_warmup_banks=%u\n", audioWarmupBanks);
    std::fprintf(marker, "audio_warmup_sequences=%u\n", audioWarmupSequences);
    std::fprintf(marker, "reserved_texture_slots=%u\n", reservedTextureSlots);
    std::fprintf(marker, "texture_pair_limit=%u\n", static_cast<unsigned>(VITAKART_TEXTURE_PAIR_LIMIT));
    std::fprintf(marker, "total_us=%llu\n", static_cast<unsigned long long>(totalUs));
    std::fprintf(marker, "total_ms=%llu\n", static_cast<unsigned long long>(totalUs / 1000));
    std::fclose(marker);
}

static void WritePreloadReentrySummary(const char* reason, uint32_t residentResources) {
    EnsureVitaKartDataDir();
    FILE* summary = std::fopen("ux0:data/vitakart64/preload-reentry.txt", "w");
    if (summary == nullptr) {
        return;
    }

    std::fprintf(summary, "preload_reentry_skipped=1\n");
    std::fprintf(summary, "preload_reentry_reason=%s\n", reason != nullptr ? reason : "unknown");
    std::fprintf(summary, "resident_resources=%u\n", residentResources);
    std::fclose(summary);
}

} // namespace

namespace VitaPreload {

void WarmRuntimeResources() {
    if (!sResidentResources.empty()) {
        WritePreloadReentrySummary("already_resident", static_cast<uint32_t>(sResidentResources.size()));
        return;
    }

    const auto context = Ship::Context::GetInstance();
    const auto resourceManager = context != nullptr ? context->GetResourceManager() : nullptr;
    const auto archiveManager = resourceManager != nullptr ? resourceManager->GetArchiveManager() : nullptr;
    Fast::Interpreter* interpreter = GetInterpreter();
    if (archiveManager == nullptr || interpreter == nullptr) {
        WritePreloadSkippedSummary("missing_runtime_context", 0);
        return;
    }

    if (const auto renderingApi = interpreter->GetCurrentRenderingAPI(); renderingApi != nullptr) {
        renderingApi->ReserveTextureSlots(kVitaTexturePreloadSlots);
    }

    const bool preloadReadyMarkerPresentBeforeRun = FileExists("ux0:data/vitakart64/preload-ready.marker");
    const uint64_t preloadStartedAt = sceKernelGetProcessTimeWide();
    VitaLoadingScreen::SetStage("PRELOADING COMPLETE GAME", "INDEXING ALL RUNTIME RESOURCES", 960);

    std::vector<std::string> files;
    std::unordered_set<std::string> seenFiles;
    files.reserve(32768);
    seenFiles.reserve(32768);
    for (const char* pattern : kRuntimeGroups) {
        const auto group = archiveManager->ListFiles(pattern);
        if (group != nullptr) {
            for (const std::string& file : *group) {
                if (seenFiles.insert(file).second) {
                    files.push_back(file);
                }
            }
        }
    }

    std::stable_sort(files.begin(), files.end(), [](const std::string& lhs, const std::string& rhs) {
        const int lhsPriority = RuntimePreloadPriority(lhs);
        const int rhsPriority = RuntimePreloadPriority(rhs);
        if (lhsPriority != rhsPriority) {
            return lhsPriority < rhsPriority;
        }
        return lhs < rhs;
    });

    sResidentResources.reserve(files.size() + 4096);
    std::vector<TextureEntry> textures;
    textures.reserve(files.size());
    uint32_t gpuTextures = 0;
    uint32_t skippedTextures = 0;
    uint32_t palettedGpuTextures = 0;
    uint32_t paletteResources = 0;
    uint32_t textureResources = 0;
    uint32_t modelResources = 0;
    uint32_t audioResources = 0;
    uint32_t otherResources = 0;
    uint32_t audioWarmupBanks = 0;
    uint32_t audioWarmupSequences = 0;
    PalettedWarmupStats palettedWarmupStats;
    std::array<uint32_t, 7> preloadPriorityCounts = {};
    std::array<uint64_t, 7> preloadPriorityTimeUs = {};
    std::array<uint64_t, 7> preloadPriorityGpuTimeUs = {};
    char detail[160];

    for (size_t i = 0; i < files.size(); i++) {
        const int preloadPriority = RuntimePreloadPriority(files[i]);
        const uint64_t resourceLoadStartedAt = sceKernelGetProcessTimeWide();
        const auto resource = resourceManager->LoadResource(files[i]);
        const uint64_t resourceLoadFinishedAt = sceKernelGetProcessTimeWide();
        if (resource != nullptr) {
            sResidentResources.push_back(resource);
            if (preloadPriority >= 0 && static_cast<size_t>(preloadPriority) < preloadPriorityCounts.size()) {
                preloadPriorityCounts[static_cast<size_t>(preloadPriority)]++;
                preloadPriorityTimeUs[static_cast<size_t>(preloadPriority)] +=
                    resourceLoadFinishedAt - resourceLoadStartedAt;
            }
            if (StartsWith(files[i], "textures/")) {
                textureResources++;
            } else if (StartsWith(files[i], "models/")) {
                modelResources++;
            } else if (StartsWith(files[i], "sound/")) {
                audioResources++;
            } else {
                otherResources++;
            }

            const auto texture = std::dynamic_pointer_cast<Fast::Texture>(resource);
            if (texture != nullptr) {
                textures.push_back({ files[i], texture });
                if (IsPaletteResourcePath(files[i])) {
                    paletteResources++;
                } else if (IsCiTexture(texture)) {
                    skippedTextures++;
                } else {
                    const uint64_t gpuUploadStartedAt = sceKernelGetProcessTimeWide();
                    const bool uploaded = interpreter->PreloadTextureResource(texture);
                    const uint64_t gpuUploadFinishedAt = sceKernelGetProcessTimeWide();
                    if (preloadPriority >= 0 && static_cast<size_t>(preloadPriority) < preloadPriorityGpuTimeUs.size()) {
                        preloadPriorityGpuTimeUs[static_cast<size_t>(preloadPriority)] +=
                            gpuUploadFinishedAt - gpuUploadStartedAt;
                    }
                    if (uploaded) {
                        gpuTextures++;
                    } else {
                        skippedTextures++;
                    }
                }
            }
        }

        if ((i & 63U) == 0 || i + 1 == files.size()) {
            std::snprintf(detail, sizeof(detail), "RES %u/%u   TEX %u   MDL %u   AUD %u   GPU %u",
                          static_cast<unsigned>(i + 1), static_cast<unsigned>(files.size()), textureResources,
                          modelResources, audioResources, gpuTextures);
            const uint32_t progress =
                960U + static_cast<uint32_t>(((i + 1) * 38U) / (files.empty() ? 1U : files.size()));
            VitaLoadingScreen::SetStage("PRELOADING COMPLETE GAME", detail, progress);
        }
    }

    const uint64_t resourcePhaseFinishedAt = sceKernelGetProcessTimeWide();
    palettedGpuTextures = WarmPalettedTexturePairs(interpreter, resourceManager, textures, palettedWarmupStats);
    const uint64_t palettedPhaseFinishedAt = sceKernelGetProcessTimeWide();
    WarmAudioRuntimeTables(audioWarmupBanks, audioWarmupSequences);
    const uint64_t audioPhaseFinishedAt = sceKernelGetProcessTimeWide();
    gpuTextures += palettedGpuTextures;

    if (const auto renderingApi = interpreter->GetCurrentRenderingAPI(); renderingApi != nullptr) {
        renderingApi->InvalidateTextureBindings();
    }
    const uint32_t deferredTextures =
        skippedTextures > palettedGpuTextures ? skippedTextures - palettedGpuTextures : 0;
    std::snprintf(detail, sizeof(detail), "%u RES   %u GPU   %u CI/TLUT   %u TLUT   %u AUD   %u BNK   %u SEQ   %u MDL   %u OTHER   %u DEF",
                  static_cast<unsigned>(sResidentResources.size()), gpuTextures, palettedGpuTextures,
                  paletteResources, audioResources, audioWarmupBanks, audioWarmupSequences, modelResources,
                  otherResources, deferredTextures);
    WritePreloadSummary(static_cast<uint32_t>(sResidentResources.size()), textureResources, modelResources,
                        audioResources, otherResources, gpuTextures, palettedGpuTextures, paletteResources,
                        deferredTextures, kVitaTexturePreloadSlots, preloadReadyMarkerPresentBeforeRun,
                        palettedWarmupStats,
                        preloadPriorityCounts,
                        preloadPriorityTimeUs, preloadPriorityGpuTimeUs, audioWarmupBanks, audioWarmupSequences,
                        resourcePhaseFinishedAt - preloadStartedAt,
                        palettedPhaseFinishedAt - resourcePhaseFinishedAt,
                        audioPhaseFinishedAt - palettedPhaseFinishedAt,
                        audioPhaseFinishedAt - preloadStartedAt);
    WritePreloadReadyMarker(static_cast<uint32_t>(sResidentResources.size()), gpuTextures, palettedGpuTextures,
                            kVitaTexturePreloadSlots, palettedWarmupStats, audioWarmupBanks, audioWarmupSequences,
                            audioPhaseFinishedAt - preloadStartedAt);
    VitaLoadingScreen::SetStage("RUNTIME CACHE READY", detail, 999);
}

} // namespace VitaPreload

#endif
