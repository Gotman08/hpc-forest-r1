/*
  Copyright (c) 2010-2023, Intel Corporation

  SPDX-License-Identifier: BSD-3-Clause
*/

#include <math.h>
#include <cstddef>
#include <vector>

#define NOISE_PERM_SIZE 256

static int NoisePerm[2 * NOISE_PERM_SIZE] = {
    151, 160, 137, 91, 90, 15, 131, 13, 201, 95, 96, 53, 194, 233, 7, 225,
    140, 36, 103, 30, 69, 142, 8, 99, 37, 240, 21, 10, 23, 190, 6, 148,
    247, 120, 234, 75, 0, 26, 197, 62, 94, 252, 219, 203, 117, 35, 11, 32,
    57, 177, 33, 88, 237, 149, 56, 87, 174, 20, 125, 136, 171, 168, 68, 175,
    74, 165, 71, 134, 139, 48, 27, 166, 77, 146, 158, 231, 83, 111, 229, 122,
    60, 211, 133, 230, 220, 105, 92, 41, 55, 46, 245, 40, 244, 102, 143, 54,
    65, 25, 63, 161, 1, 216, 80, 73, 209, 76, 132, 187, 208, 89, 18, 169,
    200, 196, 135, 130, 116, 188, 159, 86, 164, 100, 109, 198, 173, 186, 3, 64,
    52, 217, 226, 250, 124, 123, 5, 202, 38, 147, 118, 126, 255, 82, 85, 212,
    207, 206, 59, 227, 47, 16, 58, 17, 182, 189, 28, 42, 223, 183, 170, 213,
    119, 248, 152, 2, 44, 154, 163, 70, 221, 153, 101, 155, 167, 43, 172, 9,
    129, 22, 39, 253, 19, 98, 108, 110, 79, 113, 224, 232, 178, 185, 112, 104,
    218, 246, 97, 228, 251, 34, 242, 193, 238, 210, 144, 12, 191, 179, 162, 241,
    81, 51, 145, 235, 249, 14, 239, 107, 49, 192, 214, 31, 181, 199, 106, 157,
    184, 84, 204, 176, 115, 121, 50, 45, 127, 4, 150, 254, 138, 236, 205, 93,
    222, 114, 67, 29, 24, 72, 243, 141, 128, 195, 78, 66, 215, 61, 156, 180,
    151, 160, 137, 91, 90, 15, 131, 13, 201, 95, 96, 53, 194, 233, 7, 225,
    140, 36, 103, 30, 69, 142, 8, 99, 37, 240, 21, 10, 23, 190, 6, 148,
    247, 120, 234, 75, 0, 26, 197, 62, 94, 252, 219, 203, 117, 35, 11, 32,
    57, 177, 33, 88, 237, 149, 56, 87, 174, 20, 125, 136, 171, 168, 68, 175,
    74, 165, 71, 134, 139, 48, 27, 166, 77, 146, 158, 231, 83, 111, 229, 122,
    60, 211, 133, 230, 220, 105, 92, 41, 55, 46, 245, 40, 244, 102, 143, 54,
    65, 25, 63, 161, 1, 216, 80, 73, 209, 76, 132, 187, 208, 89, 18, 169,
    200, 196, 135, 130, 116, 188, 159, 86, 164, 100, 109, 198, 173, 186, 3, 64,
    52, 217, 226, 250, 124, 123, 5, 202, 38, 147, 118, 126, 255, 82, 85, 212,
    207, 206, 59, 227, 47, 16, 58, 17, 182, 189, 28, 42, 223, 183, 170, 213,
    119, 248, 152, 2, 44, 154, 163, 70, 221, 153, 101, 155, 167, 43, 172, 9,
    129, 22, 39, 253, 19, 98, 108, 110, 79, 113, 224, 232, 178, 185, 112, 104,
    218, 246, 97, 228, 251, 34, 242, 193, 238, 210, 144, 12, 191, 179, 162, 241,
    81, 51, 145, 235, 249, 14, 239, 107, 49, 192, 214, 31, 181, 199, 106, 157,
    184, 84, 204, 176, 115, 121, 50, 45, 127, 4, 150, 254, 138, 236, 205, 93,
    222, 114, 67, 29, 24, 72, 243, 141, 128, 195, 78, 66, 215, 61, 156, 180};

inline float Clamp(float v, float low, float high) { return v < low ? low : ((v > high) ? high : v); }

inline float SmoothStep(float low, float high, float value) {
    float v = Clamp((value - low) / (high - low), 0.f, 1.f);
    return v * v * (-2.f * v + 3.f);
}

inline int Floor2Int(float val) { return (int)floorf(val); }

inline float Grad(int x, int y, int z, float dx, float dy, float dz) {
    int h = NoisePerm[NoisePerm[NoisePerm[x] + y] + z];
    h &= 15;
    float u = h < 8 || h == 12 || h == 13 ? dx : dy;
    float v = h < 4 || h == 12 || h == 13 ? dy : dz;
    return ((h & 1) ? -u : u) + ((h & 2) ? -v : v);
}

inline float NoiseWeight(float t) {
    float t3 = t * t * t;
    float t4 = t3 * t;
    return 6.f * t4 * t - 15.f * t4 + 10.f * t3;
}

inline float Lerp(float t, float low, float high) { return (1.f - t) * low + t * high; }

static float NoiseFromState(int ix, int iy, int iz, float dx, float dy, float dz,
                            float wx, float wy, float wz) {
    ix &= (NOISE_PERM_SIZE - 1);
    iy &= (NOISE_PERM_SIZE - 1);
    iz &= (NOISE_PERM_SIZE - 1);
    float w000 = Grad(ix, iy, iz, dx, dy, dz);
    float w100 = Grad(ix + 1, iy, iz, dx - 1, dy, dz);
    float w010 = Grad(ix, iy + 1, iz, dx, dy - 1, dz);
    float w110 = Grad(ix + 1, iy + 1, iz, dx - 1, dy - 1, dz);
    float w001 = Grad(ix, iy, iz + 1, dx, dy, dz - 1);
    float w101 = Grad(ix + 1, iy, iz + 1, dx - 1, dy, dz - 1);
    float w011 = Grad(ix, iy + 1, iz + 1, dx, dy - 1, dz - 1);
    float w111 = Grad(ix + 1, iy + 1, iz + 1, dx - 1, dy - 1, dz - 1);

    float x00 = Lerp(wx, w000, w100);
    float x10 = Lerp(wx, w010, w110);
    float x01 = Lerp(wx, w001, w101);
    float x11 = Lerp(wx, w011, w111);
    float y0 = Lerp(wy, x00, x10);
    float y1 = Lerp(wy, x01, x11);
    return Lerp(wz, y0, y1);
}

static float TurbulenceWithWeights(float x, float y,
                                   const float* xWeightByOctave, std::size_t xStride,
                                   const float* yWeightByOctave, std::size_t yStride,
                                   const int zCell[8], const float zOffset[8],
                                   const float zWeight[8]) {
    float omega = 0.6;
    float sum = 0., lambda = 1., o = 1.;
    for (int octave = 0; octave < 8; ++octave) {
        float scaledX = lambda * x;
        float scaledY = lambda * y;
        int ix = Floor2Int(scaledX), iy = Floor2Int(scaledY);
        float dx = scaledX - ix, dy = scaledY - iy;
        sum += fabsf(o * NoiseFromState(ix, iy, zCell[octave], dx, dy,
                                        zOffset[octave],
                                        xWeightByOctave[static_cast<std::size_t>(octave) * xStride],
                                        yWeightByOctave[static_cast<std::size_t>(octave) * yStride],
                                        zWeight[octave]));
        lambda *= 1.99f;
        o *= omega;
    }
    return sum * 0.5f;
}

void noise_serial(float x0, float y0, float x1, float y1, int width, int height, float output[]) {
    float dx = (x1 - x0) / width;
    float dy = (y1 - y0) / height;

    // Cache only the x/y smooth weights; lattice cells and fractions are recomputed per pixel.
    std::vector<float> xWeights(static_cast<std::size_t>(8) * static_cast<std::size_t>(width));
    std::vector<float> yWeights(static_cast<std::size_t>(8) * static_cast<std::size_t>(height));

    float lambda = 1.f;
    for (int octave = 0; octave < 8; ++octave) {
        const std::size_t base = static_cast<std::size_t>(octave) * static_cast<std::size_t>(width);
        for (int i = 0; i < width; ++i) {
            float x = x0 + i * dx;
            float scaledX = lambda * x;
            int ix = Floor2Int(scaledX);
            float fraction = scaledX - ix;
            xWeights[base + static_cast<std::size_t>(i)] = NoiseWeight(fraction);
        }
        lambda *= 1.99f;
    }

    lambda = 1.f;
    for (int octave = 0; octave < 8; ++octave) {
        const std::size_t base = static_cast<std::size_t>(octave) * static_cast<std::size_t>(height);
        for (int j = 0; j < height; ++j) {
            float y = y0 + j * dy;
            float scaledY = lambda * y;
            int iy = Floor2Int(scaledY);
            float fraction = scaledY - iy;
            yWeights[base + static_cast<std::size_t>(j)] = NoiseWeight(fraction);
        }
        lambda *= 1.99f;
    }

    int zCell[8];
    float zOffset[8];
    float zWeight[8];
    lambda = 1.f;
    for (int octave = 0; octave < 8; ++octave) {
        float scaledZ = lambda * 0.6f;
        zCell[octave] = Floor2Int(scaledZ);
        zOffset[octave] = scaledZ - zCell[octave];
        zWeight[octave] = NoiseWeight(zOffset[octave]);
        lambda *= 1.99f;
    }

    for (int j = 0; j < height; ++j) {
        float y = y0 + j * dy;
        const float* yWeightByOctave = &yWeights[static_cast<std::size_t>(j)];
        for (int i = 0; i < width; ++i) {
            float x = x0 + i * dx;
            const float* xWeightByOctave = &xWeights[static_cast<std::size_t>(i)];
            int index = j * width + i;
            output[index] = TurbulenceWithWeights(x, y, xWeightByOctave,
                                                   static_cast<std::size_t>(width),
                                                   yWeightByOctave,
                                                   static_cast<std::size_t>(height),
                                                   zCell, zOffset, zWeight);
        }
    }
}
#include <cstdint>
#include <cstring>
#include <cmath>
#include <algorithm>
#include <omp.h>
extern "C" void run(const void* input1,const void* input2,void* output,int n,int parameter,int threads)
{const float*a=(const float*)input1;noise_serial(a[0],a[1],a[2],a[3],n,n,(float*)output);}
