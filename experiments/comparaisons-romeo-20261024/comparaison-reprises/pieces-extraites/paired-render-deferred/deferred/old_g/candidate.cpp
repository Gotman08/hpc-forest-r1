/*
Copyright (c) 2011-2025, Intel Corporation

SPDX-License-Identifier: BSD-3-Clause
*/

#include "deferred.h"
#include "kernels_ispc.h"
#include <algorithm>
#include <assert.h>
#include <math.h>
#include <stdint.h>

#ifdef _MSC_VER
#define ISPC_IS_WINDOWS
#elif defined(__linux__) || defined(__FreeBSD__)
#define ISPC_IS_LINUX
#elif defined(__APPLE__)
#define ISPC_IS_APPLE
#else
#error "Host OS was not detected"
#endif

#ifdef ISPC_IS_LINUX
#include <malloc.h>
#endif

#define MIN_TILE_WIDTH 16
#define MIN_TILE_HEIGHT 16
#define DYNAMIC_TREE_LEVELS 5
#define DYNAMIC_MIN_LIGHTS_TO_SUBDIVIDE 1

static void *lAlignedMalloc(size_t size, int32_t alignment) {
#ifdef ISPC_IS_WINDOWS
    return _aligned_malloc(size, alignment);
#elif defined(ISPC_IS_LINUX)
    return memalign(alignment, size);
#elif defined(ISPC_IS_APPLE)
    void *mem = malloc(size + (alignment - 1) + sizeof(void *));
    char *amem = ((char *)mem) + sizeof(void *);
    amem = amem + uint32_t(alignment - (reinterpret_cast<uint64_t>(amem) & (alignment - 1)));
    ((void **)amem)[-1] = mem;
    return amem;
#else
#error "Host OS was not detected"
#endif
}

static void lAlignedFree(void *ptr) {
#ifdef ISPC_IS_WINDOWS
    _aligned_free(ptr);
#elif defined(ISPC_IS_LINUX)
    free(ptr);
#elif defined(ISPC_IS_APPLE)
    free(((void **)ptr)[-1]);
#else
#error "Host OS was not detected"
#endif
}

static void ComputeZBounds(int tileStartX, int tileEndX, int tileStartY, int tileEndY,
                           float zBuffer[], int gBufferWidth,
                           float cameraProj_33, float cameraProj_43, float cameraNear, float cameraFar,
                           float *minZ, float *maxZ) {
    float laneMinZ = cameraFar;
    float laneMaxZ = cameraNear;
    for (int y = tileStartY; y < tileEndY; ++y) {
        for (int x = tileStartX; x < tileEndX; ++x) {
            float z = zBuffer[y * gBufferWidth + x];
            float viewSpaceZ = cameraProj_43 / (z - cameraProj_33);
            if ((viewSpaceZ < cameraFar) && (viewSpaceZ >= cameraNear)) {
                laneMinZ = std::min(laneMinZ, viewSpaceZ);
                laneMaxZ = std::max(laneMaxZ, viewSpaceZ);
            }
        }
    }
    *minZ = laneMinZ;
    *maxZ = laneMaxZ;
}

static void ComputeZBoundsRow(int tileY, int tileWidth, int tileHeight, int numTilesX, int numTilesY,
                              float zBuffer[], int gBufferWidth,
                              float cameraProj_33, float cameraProj_43, float cameraNear, float cameraFar,
                              float minZArray[], float maxZArray[]) {
    for (int tileX = 0; tileX < numTilesX; ++tileX) {
        float minZ, maxZ;
        ComputeZBounds(tileX * tileWidth, tileX * tileWidth + tileWidth,
                       tileY * tileHeight, tileY * tileHeight + tileHeight,
                       zBuffer, gBufferWidth, cameraProj_33, cameraProj_43, cameraNear, cameraFar,
                       &minZ, &maxZ);
        minZArray[tileX] = minZ;
        maxZArray[tileX] = maxZ;
    }
}

class MinMaxZTree {
public:
    MinMaxZTree(int tileWidth, int tileHeight, int levels, int gBufferWidth, int gBufferHeight)
        : mTileWidth(tileWidth), mTileHeight(tileHeight), mLevels(levels) {
        mNumTilesX = gBufferWidth / mTileWidth;
        mNumTilesY = gBufferHeight / mTileHeight;
        mMinZArrays = (float **)lAlignedMalloc(sizeof(float *) * mLevels, 16);
        mMaxZArrays = (float **)lAlignedMalloc(sizeof(float *) * mLevels, 16);
        for (int i = 0; i < mLevels; ++i) {
            int x = NumTilesX(i);
            int y = NumTilesY(i);
            assert(x > 0);
            assert(y > 0);
            assert(x * (mTileWidth << i) >= gBufferWidth);
            assert(y * (mTileHeight << i) >= gBufferHeight);
            mMinZArrays[i] = (float *)lAlignedMalloc(sizeof(float) * x * y, 16);
            mMaxZArrays[i] = (float *)lAlignedMalloc(sizeof(float) * x * y, 16);
        }
    }

    void Update(float *zBuffer, int gBufferPitchInElements, float cameraProj_33, float cameraProj_43,
                float cameraNear, float cameraFar, int threads) {
        auto reduceLevelTile = [this](int level, int x, int y) {
            int destTilesX = NumTilesX(level);
            int srcLevel = level - 1;
            int srcTilesX = NumTilesX(srcLevel);
            int srcTilesY = NumTilesY(srcLevel);
            int srcX = x << 1;
            int srcY = y << 1;
            float minZ = mMinZArrays[srcLevel][srcY * srcTilesX + srcX];
            float maxZ = mMaxZArrays[srcLevel][srcY * srcTilesX + srcX];
            if (srcX + 1 < srcTilesX) {
                minZ = std::min(minZ, mMinZArrays[srcLevel][srcY * srcTilesX + srcX + 1]);
                maxZ = std::max(maxZ, mMaxZArrays[srcLevel][srcY * srcTilesX + srcX + 1]);
                if (srcY + 1 < srcTilesY) {
                    minZ = std::min(minZ, mMinZArrays[srcLevel][(srcY + 1) * srcTilesX + srcX + 1]);
                    maxZ = std::max(maxZ, mMaxZArrays[srcLevel][(srcY + 1) * srcTilesX + srcX + 1]);
                }
            }
            if (srcY + 1 < srcTilesY) {
                minZ = std::min(minZ, mMinZArrays[srcLevel][(srcY + 1) * srcTilesX + srcX]);
                maxZ = std::max(maxZ, mMaxZArrays[srcLevel][(srcY + 1) * srcTilesX + srcX]);
            }
            mMinZArrays[level][y * destTilesX + x] = minZ;
            mMaxZArrays[level][y * destTilesX + x] = maxZ;
        };
#ifdef _OPENMP
        int availableWorkers = mNumTilesY;
        if (mLevels > 1) {
            availableWorkers = std::max(availableWorkers, NumTilesX(1) * NumTilesY(1));
        }
        int workerCount = threads > 0 ? std::min(threads, availableWorkers) : 1;
        if (workerCount > 1) {
#pragma omp parallel num_threads(workerCount)
            {
#pragma omp for schedule(static)
                for (int tileY = 0; tileY < mNumTilesY; ++tileY) {
                    ComputeZBoundsRow(tileY, mTileWidth, mTileHeight, mNumTilesX, mNumTilesY,
                                      zBuffer, gBufferPitchInElements, cameraProj_33, cameraProj_43,
                                      cameraNear, cameraFar,
                                      mMinZArrays[0] + tileY * mNumTilesX,
                                      mMaxZArrays[0] + tileY * mNumTilesX);
                }
                for (int level = 1; level < mLevels; ++level) {
                    int destTilesX = NumTilesX(level);
                    int destTilesY = NumTilesY(level);
#pragma omp for collapse(2) schedule(static)
                    for (int y = 0; y < destTilesY; ++y) {
                        for (int x = 0; x < destTilesX; ++x) {
                            reduceLevelTile(level, x, y);
                        }
                    }
                }
            }
            return;
        }
#else
        (void)threads;
#endif
        for (int tileY = 0; tileY < mNumTilesY; ++tileY) {
            ComputeZBoundsRow(tileY, mTileWidth, mTileHeight, mNumTilesX, mNumTilesY,
                              zBuffer, gBufferPitchInElements, cameraProj_33, cameraProj_43,
                              cameraNear, cameraFar,
                              mMinZArrays[0] + tileY * mNumTilesX,
                              mMaxZArrays[0] + tileY * mNumTilesX);
        }
        for (int level = 1; level < mLevels; ++level) {
            int destTilesX = NumTilesX(level);
            int destTilesY = NumTilesY(level);
            for (int y = 0; y < destTilesY; ++y) {
                for (int x = 0; x < destTilesX; ++x) {
                    reduceLevelTile(level, x, y);
                }
            }
        }
    }

    ~MinMaxZTree() {
        for (int i = 0; i < mLevels; ++i) {
            lAlignedFree(mMinZArrays[i]);
            lAlignedFree(mMaxZArrays[i]);
        }
        lAlignedFree(mMinZArrays);
        lAlignedFree(mMaxZArrays);
    }

    int Levels() const { return mLevels; }
    int NumTilesX(int level = 0) const { return (mNumTilesX + (1 << level) - 1) >> level; }
    int NumTilesY(int level = 0) const { return (mNumTilesY + (1 << level) - 1) >> level; }
    int TileWidth(int level = 0) const { return mTileWidth << level; }
    int TileHeight(int level = 0) const { return mTileHeight << level; }
    float MinZ(int level, int tileX, int tileY) const {
        return mMinZArrays[level][tileY * NumTilesX(level) + tileX];
    }
    float MaxZ(int level, int tileX, int tileY) const {
        return mMaxZArrays[level][tileY * NumTilesX(level) + tileX];
    }

private:
    int mTileWidth;
    int mTileHeight;
    int mLevels;
    int mNumTilesX;
    int mNumTilesY;
    float **mMinZArrays;
    float **mMaxZArrays;
};

static MinMaxZTree *gMinMaxZTree = 0;

void InitDynamicC(InputData *input) {
    gMinMaxZTree = new MinMaxZTree(MIN_TILE_WIDTH, MIN_TILE_HEIGHT, DYNAMIC_TREE_LEVELS,
                                   input->header.framebufferWidth, input->header.framebufferHeight);
}

static void SplitTileMinMax(int tileMidX, int tileMidY,
                            float subtileMinZ[], float subtileMaxZ[],
                            int gBufferWidth, int gBufferHeight,
                            float cameraProj_11, float cameraProj_22,
                            int lightIndices[], int numLights, float light_positionView_x_array[],
                            float light_positionView_y_array[], float light_positionView_z_array[],
                            float light_attenuationEnd_array[],
                            int subtileIndices[], int subtileIndicesPitch, int subtileNumLights[]) {
    float gBufferScale_x = 0.5f * (float)gBufferWidth;
    float gBufferScale_y = 0.5f * (float)gBufferHeight;
    float frustumPlanes_xy[2] = {-(cameraProj_11 * gBufferScale_x), (cameraProj_22 * gBufferScale_y)};
    float frustumPlanes_z[2] = {tileMidX - gBufferScale_x, tileMidY - gBufferScale_y};
    for (int i = 0; i < 2; ++i) {
        float norm = 1.f / sqrtf(frustumPlanes_xy[i] * frustumPlanes_xy[i] +
                                 frustumPlanes_z[i] * frustumPlanes_z[i]);
        frustumPlanes_xy[i] *= norm;
        frustumPlanes_z[i] *= norm;
    }
    int subtileLightOffset[4] = {0, subtileIndicesPitch, 2 * subtileIndicesPitch,
                                 3 * subtileIndicesPitch};
    for (int i = 0; i < numLights; ++i) {
        int lightIndex = lightIndices[i];
        float light_positionView_x = light_positionView_x_array[lightIndex];
        float light_positionView_y = light_positionView_y_array[lightIndex];
        float light_positionView_z = light_positionView_z_array[lightIndex];
        float light_attenuationEnd = light_attenuationEnd_array[lightIndex];
        float light_attenuationEndNeg = -light_attenuationEnd;
        bool inFrustum[4];
        inFrustum[0] = (light_positionView_z - subtileMinZ[0] >= light_attenuationEndNeg) &&
                       (subtileMaxZ[0] - light_positionView_z >= light_attenuationEndNeg);
        inFrustum[1] = (light_positionView_z - subtileMinZ[1] >= light_attenuationEndNeg) &&
                       (subtileMaxZ[1] - light_positionView_z >= light_attenuationEndNeg);
        inFrustum[2] = (light_positionView_z - subtileMinZ[2] >= light_attenuationEndNeg) &&
                       (subtileMaxZ[2] - light_positionView_z >= light_attenuationEndNeg);
        inFrustum[3] = (light_positionView_z - subtileMinZ[3] >= light_attenuationEndNeg) &&
                       (subtileMaxZ[3] - light_positionView_z >= light_attenuationEndNeg);
        float dx = light_positionView_z * frustumPlanes_z[0] + light_positionView_x * frustumPlanes_xy[0];
        float dy = light_positionView_z * frustumPlanes_z[1] + light_positionView_y * frustumPlanes_xy[1];
        if (fabsf(dx) > light_attenuationEnd) {
            bool positiveX = dx > 0.0f;
            inFrustum[0] = inFrustum[0] && positiveX;
            inFrustum[1] = inFrustum[1] && !positiveX;
            inFrustum[2] = inFrustum[2] && positiveX;
            inFrustum[3] = inFrustum[3] && !positiveX;
        }
        if (fabsf(dy) > light_attenuationEnd) {
            bool positiveY = dy > 0.0f;
            inFrustum[0] = inFrustum[0] && positiveY;
            inFrustum[1] = inFrustum[1] && positiveY;
            inFrustum[2] = inFrustum[2] && !positiveY;
            inFrustum[3] = inFrustum[3] && !positiveY;
        }
        if (inFrustum[0]) subtileIndices[subtileLightOffset[0]++] = lightIndex;
        if (inFrustum[1]) subtileIndices[subtileLightOffset[1]++] = lightIndex;
        if (inFrustum[2]) subtileIndices[subtileLightOffset[2]++] = lightIndex;
        if (inFrustum[3]) subtileIndices[subtileLightOffset[3]++] = lightIndex;
    }
    subtileNumLights[0] = subtileLightOffset[0];
    subtileNumLights[1] = subtileLightOffset[1] - subtileIndicesPitch;
    subtileNumLights[2] = subtileLightOffset[2] - 2 * subtileIndicesPitch;
    subtileNumLights[3] = subtileLightOffset[3] - 3 * subtileIndicesPitch;
}

static inline float dot3(float x, float y, float z, float a, float b, float c) {
    return x * a + y * b + z * c;
}

static inline void normalize3(float x, float y, float z, float &ox, float &oy, float &oz) {
    float n = 1.f / sqrtf(x * x + y * y + z * z);
    ox = x * n;
    oy = y * n;
    oz = z * n;
}

static inline float Unorm8ToFloat32(uint8_t u) { return (float)u * (1.0f / 255.0f); }
static inline uint8_t Float32ToUnorm8(float f) { return (uint8_t)(f * 255.0f); }

static inline float half_to_float_fast(uint16_t h) {
    uint32_t hs = h & (int32_t)0x8000u;
    uint32_t he = h & (int32_t)0x7C00u;
    uint32_t hm = h & (int32_t)0x03FFu;
    uint32_t xs = hs << 16;
    int32_t xes = (int32_t)(he >> 10) - 15 + 127;
    uint32_t xe = (uint32_t)(xes << 23);
    uint32_t xm = hm << 13;
    union { uint32_t u; float f; } conv;
    conv.u = xs | xe | xm;
    return conv.f;
}

static void ShadeTileC(int32_t tileStartX, int32_t tileEndX, int32_t tileStartY, int32_t tileEndY,
                       int32_t gBufferWidth, int32_t gBufferHeight,
                       const ispc::InputDataArrays &inputData,
                       float cameraProj_11, float cameraProj_22, float cameraProj_33, float cameraProj_43,
                       int32_t tileLightIndices[], int32_t tileNumLights,
                       bool visualizeLightCount,
                       uint8_t framebuffer_r[], uint8_t framebuffer_g[], uint8_t framebuffer_b[]) {
    if (tileNumLights == 0 || visualizeLightCount) {
        uint8_t c = (uint8_t)(std::min(tileNumLights << 2, 255));
        for (int32_t y = tileStartY; y < tileEndY; ++y) {
            for (int32_t x = tileStartX; x < tileEndX; ++x) {
                int32_t framebufferIndex = y * gBufferWidth + x;
                framebuffer_r[framebufferIndex] = c;
                framebuffer_g[framebufferIndex] = c;
                framebuffer_b[framebufferIndex] = c;
            }
        }
    } else {
        float twoOverGBufferWidth = 2.0f / gBufferWidth;
        float twoOverGBufferHeight = 2.0f / gBufferHeight;
        float invCameraProj_11 = 1.0f / cameraProj_11;
        float invCameraProj_22 = 1.0f / cameraProj_22;
        for (int32_t y = tileStartY; y < tileEndY; ++y) {
            float positionScreen_y = -(((0.5f + y) * twoOverGBufferHeight) - 1.f);
            for (int32_t x = tileStartX; x < tileEndX; ++x) {
                int32_t gBufferOffset = y * gBufferWidth + x;
                float surface_positionView_x, surface_positionView_y, surface_positionView_z;
                float Vneg_x, Vneg_y, Vneg_z;
                float z = inputData.zBuffer[gBufferOffset];
                float positionScreen_x = (0.5f + (float)x) * twoOverGBufferWidth - 1.0f;
                surface_positionView_z = cameraProj_43 / (z - cameraProj_33);
                surface_positionView_x = positionScreen_x * surface_positionView_z * invCameraProj_11;
                surface_positionView_y = positionScreen_y * surface_positionView_z * invCameraProj_22;
                normalize3(surface_positionView_x, surface_positionView_y, surface_positionView_z,
                           Vneg_x, Vneg_y, Vneg_z);
                float normal_x = half_to_float_fast(inputData.normalEncoded_x[gBufferOffset]);
                float normal_y = half_to_float_fast(inputData.normalEncoded_y[gBufferOffset]);
                float f = (normal_x - normal_x * normal_x) + (normal_y - normal_y * normal_y);
                float m = sqrtf(4.0f * f - 1.0f);
                float surface_normal_x = m * (4.0f * normal_x - 2.0f);
                float surface_normal_y = m * (4.0f * normal_y - 2.0f);
                float surface_normal_z = 3.0f - 8.0f * f;
                float surface_specularAmount = half_to_float_fast(inputData.specularAmount[gBufferOffset]);
                float surface_specularPower = half_to_float_fast(inputData.specularPower[gBufferOffset]);
                float surface_albedo_x = Unorm8ToFloat32(inputData.albedo_x[gBufferOffset]);
                float surface_albedo_y = Unorm8ToFloat32(inputData.albedo_y[gBufferOffset]);
                float surface_albedo_z = Unorm8ToFloat32(inputData.albedo_z[gBufferOffset]);
                float lit_x = 0.0f, lit_y = 0.0f, lit_z = 0.0f;
                for (int32_t tileLightIndex = 0; tileLightIndex < tileNumLights; ++tileLightIndex) {
                    int32_t lightIndex = tileLightIndices[tileLightIndex];
                    float light_positionView_x = inputData.lightPositionView_x[lightIndex];
                    float light_positionView_y = inputData.lightPositionView_y[lightIndex];
                    float light_positionView_z = inputData.lightPositionView_z[lightIndex];
                    float light_attenuationEnd = inputData.lightAttenuationEnd[lightIndex];
                    float L_x = light_positionView_x - surface_positionView_x;
                    float L_y = light_positionView_y - surface_positionView_y;
                    float L_z = light_positionView_z - surface_positionView_z;
                    float distanceToLight2 = dot3(L_x, L_y, L_z, L_x, L_y, L_z);
                    float light_attenutaionEnd2 = light_attenuationEnd * light_attenuationEnd;
                    if (distanceToLight2 < light_attenutaionEnd2) {
                        float distanceToLight = sqrtf(distanceToLight2);
                        float distanceToLightRcp = 1.f / distanceToLight;
                        L_x *= distanceToLightRcp;
                        L_y *= distanceToLightRcp;
                        L_z *= distanceToLightRcp;
                        float NdotL = dot3(surface_normal_x, surface_normal_y, surface_normal_z,
                                           L_x, L_y, L_z);
                        if (NdotL > 0.0f) {
                            float light_attenuationBegin = inputData.lightAttenuationBegin[lightIndex];
                            float lightRange = light_attenuationEnd - light_attenuationBegin;
                            float falloffPosition = light_attenuationEnd - distanceToLight;
                            float attenuation = std::min(falloffPosition / lightRange, 1.0f);
                            float H_x = L_x - Vneg_x;
                            float H_y = L_y - Vneg_y;
                            float H_z = L_z - Vneg_z;
                            normalize3(H_x, H_y, H_z, H_x, H_y, H_z);
                            float NdotH = dot3(surface_normal_x, surface_normal_y, surface_normal_z,
                                               H_x, H_y, H_z);
                            NdotH = std::max(NdotH, 0.0f);
                            float specular = powf(NdotH, surface_specularPower);
                            float specularNorm = (surface_specularPower + 2.0f) * (1.0f / 8.0f);
                            float specularContrib = surface_specularAmount * specularNorm * specular;
                            float k = attenuation * NdotL * (1.0f + specularContrib);
                            float light_color_x = inputData.lightColor_x[lightIndex];
                            float light_color_y = inputData.lightColor_y[lightIndex];
                            float light_color_z = inputData.lightColor_z[lightIndex];
                            lit_x += (surface_albedo_x * light_color_x) * k;
                            lit_y += (surface_albedo_y * light_color_y) * k;
                            lit_z += (surface_albedo_z * light_color_z) * k;
                        }
                    }
                }
                float gamma = 1.0 / 2.2f;
                lit_x = powf(std::min(std::max(lit_x, 0.0f), 1.0f), gamma);
                lit_y = powf(std::min(std::max(lit_y, 0.0f), 1.0f), gamma);
                lit_z = powf(std::min(std::max(lit_z, 0.0f), 1.0f), gamma);
                framebuffer_r[gBufferOffset] = Float32ToUnorm8(lit_x);
                framebuffer_g[gBufferOffset] = Float32ToUnorm8(lit_y);
                framebuffer_b[gBufferOffset] = Float32ToUnorm8(lit_z);
            }
        }
    }
}

void ShadeDynamicTileRecurse(InputData *input, int level, int tileX, int tileY,
                             int *lightIndices, int numLights, Framebuffer *framebuffer) {
    const MinMaxZTree *minMaxZTree = gMinMaxZTree;
    if (level == 0 || numLights < DYNAMIC_MIN_LIGHTS_TO_SUBDIVIDE) {
        int width = minMaxZTree->TileWidth(level);
        int height = minMaxZTree->TileHeight(level);
        int startX = tileX * width;
        int startY = tileY * height;
        int endX = std::min(input->header.framebufferWidth, startX + width);
        int endY = std::min(input->header.framebufferHeight, startY + height);
        if (endX > startX && endY > startY) {
            ShadeTileC(startX, endX, startY, endY,
                       input->header.framebufferWidth, input->header.framebufferHeight,
                       input->arrays, input->header.cameraProj[0][0], input->header.cameraProj[1][1],
                       input->header.cameraProj[2][2], input->header.cameraProj[3][2],
                       lightIndices, numLights, VISUALIZE_LIGHT_COUNT,
                       framebuffer->r, framebuffer->g, framebuffer->b);
        }
    } else {
        --level;
        tileX <<= 1;
        tileY <<= 1;
        int width = minMaxZTree->TileWidth(level);
        int height = minMaxZTree->TileHeight(level);
        int midX = (tileX + 1) * width;
        int midY = (tileY + 1) * height;
        bool rightTileExists = tileX + 1 < minMaxZTree->NumTilesX(level);
        bool bottomTileExists = tileY + 1 < minMaxZTree->NumTilesY(level);
        float minZ[4] = {input->header.cameraFar, input->header.cameraFar,
                         input->header.cameraFar, input->header.cameraFar};
        float maxZ[4] = {input->header.cameraNear, input->header.cameraNear,
                         input->header.cameraNear, input->header.cameraNear};
        minZ[0] = minMaxZTree->MinZ(level, tileX, tileY);
        maxZ[0] = minMaxZTree->MaxZ(level, tileX, tileY);
        if (rightTileExists) {
            minZ[1] = minMaxZTree->MinZ(level, tileX + 1, tileY);
            maxZ[1] = minMaxZTree->MaxZ(level, tileX + 1, tileY);
            if (bottomTileExists) {
                minZ[3] = minMaxZTree->MinZ(level, tileX + 1, tileY + 1);
                maxZ[3] = minMaxZTree->MaxZ(level, tileX + 1, tileY + 1);
            }
        }
        if (bottomTileExists) {
            minZ[2] = minMaxZTree->MinZ(level, tileX, tileY + 1);
            maxZ[2] = minMaxZTree->MaxZ(level, tileX, tileY + 1);
        }
#ifdef ISPC_IS_WINDOWS
        __declspec(align(ALIGNMENT_BYTES))
#endif
        int subtileLightIndices[4][MAX_LIGHTS]
#ifndef ISPC_IS_WINDOWS
        __attribute__((aligned(ALIGNMENT_BYTES)))
#endif
        ;
        int subtileNumLights[4];
        SplitTileMinMax(midX, midY, minZ, maxZ,
                        input->header.framebufferWidth, input->header.framebufferHeight,
                        input->header.cameraProj[0][0], input->header.cameraProj[1][1],
                        lightIndices, numLights,
                        input->arrays.lightPositionView_x, input->arrays.lightPositionView_y,
                        input->arrays.lightPositionView_z, input->arrays.lightAttenuationEnd,
                        subtileLightIndices[0], MAX_LIGHTS, subtileNumLights);
        ShadeDynamicTileRecurse(input, level, tileX, tileY,
                                subtileLightIndices[0], subtileNumLights[0], framebuffer);
        ShadeDynamicTileRecurse(input, level, tileX + 1, tileY,
                                subtileLightIndices[1], subtileNumLights[1], framebuffer);
        ShadeDynamicTileRecurse(input, level, tileX, tileY + 1,
                                subtileLightIndices[2], subtileNumLights[2], framebuffer);
        ShadeDynamicTileRecurse(input, level, tileX + 1, tileY + 1,
                                subtileLightIndices[3], subtileNumLights[3], framebuffer);
    }
}

static int IntersectLightsWithTileMinMax(int tileStartX, int tileEndX,
                                         int tileStartY, int tileEndY,
                                         float minZ, float maxZ,
                                         int gBufferWidth, int gBufferHeight,
                                         float cameraProj_11, float cameraProj_22,
                                         int numLights, float light_positionView_x_array[],
                                         float light_positionView_y_array[], float light_positionView_z_array[],
                                         float light_attenuationEnd_array[], int tileLightIndices[]) {
    float gBufferScale_x = 0.5f * (float)gBufferWidth;
    float gBufferScale_y = 0.5f * (float)gBufferHeight;
    float frustumPlanes_xy_v[4] = {-(cameraProj_11 * gBufferScale_x),
                                   cameraProj_11 * gBufferScale_x,
                                   cameraProj_22 * gBufferScale_y,
                                   -(cameraProj_22 * gBufferScale_y)};
    float frustumPlanes_z_v[4] = {tileEndX - gBufferScale_x, -tileStartX + gBufferScale_x,
                                  tileEndY - gBufferScale_y, -tileStartY + gBufferScale_y};
    float frustumPlanes_xy[4];
    float frustumPlanes_z[4];
    for (int i = 0; i < 4; ++i) {
        float norm = 1.f / sqrtf(frustumPlanes_xy_v[i] * frustumPlanes_xy_v[i] +
                                 frustumPlanes_z_v[i] * frustumPlanes_z_v[i]);
        frustumPlanes_xy[i] = frustumPlanes_xy_v[i] * norm;
        frustumPlanes_z[i] = frustumPlanes_z_v[i] * norm;
    }
    int tileNumLights = 0;
    for (int lightIndex = 0; lightIndex < numLights; ++lightIndex) {
        float light_positionView_z = light_positionView_z_array[lightIndex];
        float light_attenuationEnd = light_attenuationEnd_array[lightIndex];
        float light_attenuationEndNeg = -light_attenuationEnd;
        float d = light_positionView_z - minZ;
        bool inFrustum = d >= light_attenuationEndNeg;
        d = maxZ - light_positionView_z;
        inFrustum = inFrustum && (d >= light_attenuationEndNeg);
        if (!inFrustum) continue;
        float light_positionView_x = light_positionView_x_array[lightIndex];
        float light_positionView_y = light_positionView_y_array[lightIndex];
        d = light_positionView_z * frustumPlanes_z[0] + light_positionView_x * frustumPlanes_xy[0];
        inFrustum = inFrustum && (d >= light_attenuationEndNeg);
        d = light_positionView_z * frustumPlanes_z[1] + light_positionView_x * frustumPlanes_xy[1];
        inFrustum = inFrustum && (d >= light_attenuationEndNeg);
        d = light_positionView_z * frustumPlanes_z[2] + light_positionView_y * frustumPlanes_xy[2];
        inFrustum = inFrustum && (d >= light_attenuationEndNeg);
        d = light_positionView_z * frustumPlanes_z[3] + light_positionView_y * frustumPlanes_xy[3];
        inFrustum = inFrustum && (d >= light_attenuationEndNeg);
        if (inFrustum) tileLightIndices[tileNumLights++] = lightIndex;
    }
    return tileNumLights;
}

void ShadeDynamicTile(InputData *input, int level, int tileX, int tileY, Framebuffer *framebuffer) {
    const MinMaxZTree *minMaxZTree = gMinMaxZTree;
    int width = minMaxZTree->TileWidth(level);
    int height = minMaxZTree->TileHeight(level);
    float minZ = minMaxZTree->MinZ(level, tileX, tileY);
    float maxZ = minMaxZTree->MaxZ(level, tileX, tileY);
    int startX = tileX * width;
    int startY = tileY * height;
    int endX = std::min(input->header.framebufferWidth, startX + width);
    int endY = std::min(input->header.framebufferHeight, startY + height);
#ifdef ISPC_IS_WINDOWS
    __declspec(align(ALIGNMENT_BYTES))
#endif
    int lightIndices[MAX_LIGHTS]
#ifndef ISPC_IS_WINDOWS
    __attribute__((aligned(ALIGNMENT_BYTES)))
#endif
    ;
    int numLights = IntersectLightsWithTileMinMax(
        startX, endX, startY, endY, minZ, maxZ,
        input->header.framebufferWidth, input->header.framebufferHeight,
        input->header.cameraProj[0][0], input->header.cameraProj[1][1], MAX_LIGHTS,
        input->arrays.lightPositionView_x, input->arrays.lightPositionView_y,
        input->arrays.lightPositionView_z, input->arrays.lightAttenuationEnd, lightIndices);
    ShadeDynamicTileRecurse(input, level, tileX, tileY, lightIndices, numLights, framebuffer);
}

void DispatchDynamicC(InputData *input, Framebuffer *framebuffer, int threads) {
    MinMaxZTree *minMaxZTree = gMinMaxZTree;
    minMaxZTree->Update(input->arrays.zBuffer, input->header.framebufferWidth,
                        input->header.cameraProj[2][2], input->header.cameraProj[3][2],
                        input->header.cameraNear, input->header.cameraFar, threads);
    int rootLevel = minMaxZTree->Levels() - 1;
    int rootTilesX = minMaxZTree->NumTilesX(rootLevel);
    int rootTilesY = minMaxZTree->NumTilesY(rootLevel);
    int rootTiles = rootTilesX * rootTilesY;
    auto shadeRootTile = [&](int g) {
        uint32_t tileY = (uint32_t)(g / rootTilesX);
        uint32_t tileX = (uint32_t)(g % rootTilesX);
        ShadeDynamicTile(input, rootLevel, (int)tileX, (int)tileY, framebuffer);
    };
#ifdef _OPENMP
    int workerCount = threads > 0 ? std::min(threads, rootTiles) : 1;
    if (workerCount > 1) {
#pragma omp parallel for schedule(dynamic, 1) num_threads(workerCount)
        for (int g = 0; g < rootTiles; ++g) shadeRootTile(g);
    } else
#endif
    {
#ifndef _OPENMP
        (void)threads;
#endif
        for (int g = 0; g < rootTiles; ++g) shadeRootTile(g);
    }
}

#include <cstring>
#include "render_context.h"
extern "C" void run(RenderInput *c, float *image, int *ids, int threads) {
    (void)image;
    (void)ids;
    auto input = (InputData *)c->deferred;
    if (!gMinMaxZTree) InitDynamicC(input);
    DispatchDynamicC(input, (Framebuffer *)c->frame, threads);
}
