/*
  Copyright (c) 2010-2023, Intel Corporation

  SPDX-License-Identifier: BSD-3-Clause
*/

#include <math.h>
#include <cstddef>
#include <vector>
#include <cstdint>
#include <cstring>
#include <cmath>
#include <algorithm>
#include <omp.h>

#define NOISE_PERM_SIZE 256
#define NOISE_PERM_VALUES 151,160,137,91,90,15,131,13,201,95,96,53,194,233,7,225,140,36,103,30,69,142,8,99,37,240,21,10,23,190,6,148,247,120,234,75,0,26,197,62,94,252,219,203,117,35,11,32,57,177,33,88,237,149,56,87,174,20,125,136,171,168,68,175,74,165,71,134,139,48,27,166,77,146,158,231,83,111,229,122,60,211,133,230,220,105,92,41,55,46,245,40,244,102,143,54,65,25,63,161,1,216,80,73,209,76,132,187,208,89,18,169,200,196,135,130,116,188,159,86,164,100,109,198,173,186,3,64,52,217,226,250,124,123,5,202,38,147,118,126,255,82,85,212,207,206,59,227,47,16,58,17,182,189,28,42,223,183,170,213,119,248,152,2,44,154,163,70,221,153,101,155,167,43,172,9,129,22,39,253,19,98,108,110,79,113,224,232,178,185,112,104,218,246,97,228,251,34,242,193,238,210,144,12,191,179,162,241,81,51,145,235,249,14,239,107,49,192,214,31,181,199,106,157,184,84,204,176,115,121,50,45,127,4,150,254,138,236,205,93,222,114,67,29,24,72,243,141,128,195,78,66,215,61,156,180
static int NoisePerm[2 * NOISE_PERM_SIZE] = {NOISE_PERM_VALUES, NOISE_PERM_VALUES};
#undef NOISE_PERM_VALUES

inline float Clamp(float v, float low, float high) { return v < low ? low : ((v > high) ? high : v); }

inline float SmoothStep(float low, float high, float value) {
    float v = Clamp((value - low) / (high - low), 0.f, 1.f);
    return v * v * (-2.f * v + 3.f);
}

inline int Floor2Int(float val) { return (int)floorf(val); }

inline float GradFromHash(int h, float dx, float dy, float dz) {
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

struct AxisState {
    int cell;
    float fraction;
    float weight;
};

static AxisState MakeAxisState(float value) {
    int cell = Floor2Int(value);
    float fraction = value - cell;
    cell &= (NOISE_PERM_SIZE - 1);

    AxisState state;
    state.cell = cell;
    state.fraction = fraction;
    state.weight = NoiseWeight(fraction);
    return state;
}

static float NoiseFromState(const AxisState& x, const AxisState& y, const AxisState& z) {
    int ix = x.cell, iy = y.cell, iz = z.cell;
    float dx = x.fraction, dy = y.fraction, dz = z.fraction;

    int px0 = NoisePerm[ix];
    int px1 = NoisePerm[ix + 1];
    int p00 = NoisePerm[px0 + iy];
    int p10 = NoisePerm[px1 + iy];
    int p01 = NoisePerm[px0 + iy + 1];
    int p11 = NoisePerm[px1 + iy + 1];

    int h000 = NoisePerm[p00 + iz];
    int h100 = NoisePerm[p10 + iz];
    int h010 = NoisePerm[p01 + iz];
    int h110 = NoisePerm[p11 + iz];
    int h001 = NoisePerm[p00 + iz + 1];
    int h101 = NoisePerm[p10 + iz + 1];
    int h011 = NoisePerm[p01 + iz + 1];
    int h111 = NoisePerm[p11 + iz + 1];

    float w000 = GradFromHash(h000, dx, dy, dz);
    float w100 = GradFromHash(h100, dx - 1, dy, dz);
    float w010 = GradFromHash(h010, dx, dy - 1, dz);
    float w110 = GradFromHash(h110, dx - 1, dy - 1, dz);
    float w001 = GradFromHash(h001, dx, dy, dz - 1);
    float w101 = GradFromHash(h101, dx - 1, dy, dz - 1);
    float w011 = GradFromHash(h011, dx, dy - 1, dz - 1);
    float w111 = GradFromHash(h111, dx - 1, dy - 1, dz - 1);

    float x00 = Lerp(x.weight, w000, w100);
    float x10 = Lerp(x.weight, w010, w110);
    float x01 = Lerp(x.weight, w001, w101);
    float x11 = Lerp(x.weight, w011, w111);
    float y0 = Lerp(y.weight, x00, x10);
    float y1 = Lerp(y.weight, x01, x11);
    return Lerp(z.weight, y0, y1);
}

void noise_serial(float x0, float y0, float x1, float y1, int width, int height, float output[]) {
    const int octaves = 8;
    float dx = (x1 - x0) / width;
    float dy = (y1 - y0) / height;

    std::vector<AxisState> xStates(static_cast<std::size_t>(octaves) * static_cast<std::size_t>(width));
    std::vector<AxisState> yStates(static_cast<std::size_t>(octaves) * static_cast<std::size_t>(height));
    AxisState zStates[octaves];
    float amplitudes[octaves];

    float omega = 0.6;
    float lambda = 1., o = 1.;
    for (int octave = 0; octave < octaves; ++octave) {
        amplitudes[octave] = o;
        zStates[octave] = MakeAxisState(lambda * 0.6f);

        const std::size_t xBase = static_cast<std::size_t>(octave) * static_cast<std::size_t>(width);
        for (int i = 0; i < width; ++i) {
            float x = x0 + i * dx;
            xStates[xBase + static_cast<std::size_t>(i)] = MakeAxisState(lambda * x);
        }

        const std::size_t yBase = static_cast<std::size_t>(octave) * static_cast<std::size_t>(height);
        for (int j = 0; j < height; ++j) {
            float y = y0 + j * dy;
            yStates[yBase + static_cast<std::size_t>(j)] = MakeAxisState(lambda * y);
        }

        lambda *= 1.99f;
        o *= omega;
    }

    for (int j = 0; j < height; ++j) {
        for (int i = 0; i < width; ++i) {
            float sum = 0.;
            for (int octave = 0; octave < octaves; ++octave) {
                const AxisState& x = xStates[static_cast<std::size_t>(octave) * static_cast<std::size_t>(width) + static_cast<std::size_t>(i)];
                const AxisState& y = yStates[static_cast<std::size_t>(octave) * static_cast<std::size_t>(height) + static_cast<std::size_t>(j)];
                sum += fabsf(amplitudes[octave] * NoiseFromState(x, y, zStates[octave]));
            }
            output[j * width + i] = sum * 0.5f;
        }
    }
}

extern "C" void run(const void* input1, const void* input2, void* output, int n, int parameter, int threads) {
    const float* a = static_cast<const float*>(input1);
    noise_serial(a[0], a[1], a[2], a[3], n, n, static_cast<float*>(output));
}
