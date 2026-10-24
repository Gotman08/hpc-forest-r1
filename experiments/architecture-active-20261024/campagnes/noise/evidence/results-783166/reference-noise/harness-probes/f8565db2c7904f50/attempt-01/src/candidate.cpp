/*
  Copyright (c) 2010-2023, Intel Corporation

  SPDX-License-Identifier: BSD-3-Clause
*/

#include <math.h>

#define NOISE_PERM_SIZE 256

static int NoisePerm[2 * NOISE_PERM_SIZE] = {
    151, 160, 137, 91,  90,  15,  131, 13,  201, 95,  96,  53,  194, 233, 7,   225, 140, 36,  103, 30,  69,  142, 8,
    99,  37,  240, 21,  10,  23,  190, 6,   148, 247, 120, 234, 75,  0,   26,  197, 62,  94,  252, 219, 203, 117, 35,
    11,  32,  57,  177, 33,  88,  237, 149, 56,  87,  174, 20,  125, 136, 171, 168, 68,  175, 74,  165, 71,  134, 139,
    48,  27,  166, 77,  146, 158, 231, 83,  111, 229, 122, 60,  211, 133, 230, 220, 105, 92,  41,  55,  46,  245, 40,
    244, 102, 143, 54,  65,  25,  63,  161, 1,   216, 80,  73,  209, 76,  132, 187, 208, 89,  18,  169, 200, 196, 135,
    130, 116, 188, 159, 86,  164, 100, 109, 198, 173, 186, 3,   64,  52,  217, 226, 250, 124, 123, 5,   202, 38,  147,
    118, 126, 255, 82,  85,  212, 207, 206, 59,  227, 47,  16,  58,  17,  182, 189, 28,  42,  223, 183, 170, 213, 119,
    248, 152, 2,   44,  154, 163, 70,  221, 153, 101, 155, 167, 43,  172, 9,   129, 22,  39,  253, 19,  98,  108, 110,
    79,  113, 224, 232, 178, 185, 112, 104, 218, 246, 97,  228, 251, 34,  242, 193, 238, 210, 144, 12,  191, 179, 162,
    241, 81,  51,  145, 235, 249, 14,  239, 107, 49,  192, 214, 31,  181, 199, 106, 157, 184, 84,  204, 176, 115, 121,
    50,  45,  127, 4,   150, 254, 138, 236, 205, 93,  222, 114, 67,  29,  24,  72,  243, 141, 128, 195, 78,  66,  215,
    61,  156, 180, 151, 160, 137, 91,  90,  15,  131, 13,  201, 95,  96,  53,  194, 233, 7,   225, 140, 36,  103, 30,
    69,  142, 8,   99,  37,  240, 21,  10,  23,  190, 6,   148, 247, 120, 234, 75,  0,   26,  197, 62,  94,  252, 219,
    203, 117, 35,  11,  32,  57,  177, 33,  88,  237, 149, 56,  87,  174, 20,  125, 136, 171, 168, 68,  175, 74,  165,
    71,  134, 139, 48,  27,  166, 77,  146, 158, 231, 83,  111, 229, 122, 60,  211, 133, 230, 220, 105, 92,  41,  55,
    46,  245, 40,  244, 102, 143, 54,  65,  25,  63,  161, 1,   216, 80,  73,  209, 76,  132, 187, 208, 89,  18,  169,
    200, 196, 135, 130, 116, 188, 159, 86,  164, 100, 109, 198, 173, 186, 3,   64,  52,  217, 226, 250, 124, 123, 5,
    202, 38,  147, 118, 126, 255, 82,  85,  212, 207, 206, 59,  227, 47,  16,  58,  17,  182, 189, 28,  42,  223, 183,
    170, 213, 119, 248, 152, 2,   44,  154, 163, 70,  221, 153, 101, 155, 167, 43,  172, 9,   129, 22,  39,  253, 19,
    98,  108, 110, 79,  113, 224, 232, 178, 185, 112, 104, 218, 246, 97,  228, 251, 34,  242, 193, 238, 210, 144, 12,
    191, 179, 162, 241, 81,  51,  145, 235, 249, 14,  239, 107, 49,  192, 214, 31,  181, 199, 106, 157, 184, 84,  204,
    176, 115, 121, 50,  45,  127, 4,   150, 254, 138, 236, 205, 93,  222, 114, 67,  29,  24,  72,  243, 141, 128, 195,
    78,  66,  215, 61,  156, 180};

inline float Clamp(float v, float low, float high) { return v < low ? low : ((v > high) ? high : v); }

inline float SmoothStep(float low, float high, float value) {
    float v = Clamp((value - low) / (high - low), 0.f, 1.f);
    return v * v * (-2.f * v + 3.f);
}

inline int Floor2Int(float val) { return (int)floorf(val); }

struct NoiseAxisState {
    int cell;
    float fraction;
};

inline NoiseAxisState MakeNoiseAxisState(float coordinate) {
    int cell = Floor2Int(coordinate);
    NoiseAxisState state = {cell & (NOISE_PERM_SIZE - 1), coordinate - cell};
    return state;
}

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

static float NoiseFromAxes(const NoiseAxisState& x, const NoiseAxisState& y, float z) {
    int ix = x.cell, iy = y.cell, iz = Floor2Int(z);
    float dx = x.fraction, dy = y.fraction, dz = z - iz;

    iz &= (NOISE_PERM_SIZE - 1);
    float w000 = Grad(ix, iy, iz, dx, dy, dz);
    float w100 = Grad(ix + 1, iy, iz, dx - 1, dy, dz);
    float w010 = Grad(ix, iy + 1, iz, dx, dy - 1, dz);
    float w110 = Grad(ix + 1, iy + 1, iz, dx - 1, dy - 1, dz);
    float w001 = Grad(ix, iy, iz + 1, dx, dy, dz - 1);
    float w101 = Grad(ix + 1, iy, iz + 1, dx - 1, dy, dz - 1);
    float w011 = Grad(ix, iy + 1, iz + 1, dx, dy - 1, dz - 1);
    float w111 = Grad(ix + 1, iy + 1, iz + 1, dx - 1, dy - 1, dz - 1);

    float wx = NoiseWeight(dx), wy = NoiseWeight(dy), wz = NoiseWeight(dz);
    float x00 = Lerp(wx, w000, w100);
    float x10 = Lerp(wx, w010, w110);
    float x01 = Lerp(wx, w001, w101);
    float x11 = Lerp(wx, w011, w111);
    float y0 = Lerp(wy, x00, x10);
    float y1 = Lerp(wy, x01, x11);
    return Lerp(wz, y0, y1);
}

#include <cstddef>
#include <cstdint>
#include <cstring>
#include <cmath>
#include <algorithm>
#include <vector>
#include <omp.h>

void noise_serial(float x0, float y0, float x1, float y1, int width, int height, float output[]) {
    float dx = (x1 - x0) / width;
    float dy = (y1 - y0) / height;

    const int octaves = 8;
    std::vector<NoiseAxisState> x_state(static_cast<std::size_t>(width) * octaves);
    std::vector<NoiseAxisState> y_state(static_cast<std::size_t>(height) * octaves);

    float lambda = 1.f;
    for (int octave = 0; octave < octaves; ++octave) {
        const std::size_t x_base = static_cast<std::size_t>(octave) * width;
        const std::size_t y_base = static_cast<std::size_t>(octave) * height;
        for (int i = 0; i < width; ++i) {
            float x = x0 + i * dx;
            x_state[x_base + static_cast<std::size_t>(i)] = MakeNoiseAxisState(lambda * x);
        }
        for (int j = 0; j < height; ++j) {
            float y = y0 + j * dy;
            y_state[y_base + static_cast<std::size_t>(j)] = MakeNoiseAxisState(lambda * y);
        }
        lambda *= 1.99f;
    }

    for (int j = 0; j < height; ++j) {
        for (int i = 0; i < width; ++i) {
            float sum = 0.f, pixel_lambda = 1.f, o = 1.f;
            float omega = 0.6;
            for (int octave = 0; octave < octaves; ++octave) {
                const std::size_t x_index = static_cast<std::size_t>(octave) * width + i;
                const std::size_t y_index = static_cast<std::size_t>(octave) * height + j;
                sum += fabsf(o * NoiseFromAxes(x_state[x_index], y_state[y_index], pixel_lambda * 0.6f));
                pixel_lambda *= 1.99f;
                o *= omega;
            }
            output[j * width + i] = sum * 0.5f;
        }
    }
}

extern "C" void run(const void* input1, const void* input2, void* output, int n, int parameter, int threads) {
    const float* a = (const float*)input1;
    noise_serial(a[0], a[1], a[2], a[3], n, n, (float*)output);
}
