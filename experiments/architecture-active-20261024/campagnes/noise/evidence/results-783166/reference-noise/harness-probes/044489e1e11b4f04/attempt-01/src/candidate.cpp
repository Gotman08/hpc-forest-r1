/*
  Copyright (c) 2010-2023, Intel Corporation

  SPDX-License-Identifier: BSD-3-Clause
*/

#include <math.h>
#include <immintrin.h>

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

static float Noise(float x, float y, float z) {
    // Compute noise cell coordinates and offsets
    int ix = Floor2Int(x), iy = Floor2Int(y), iz = Floor2Int(z);
    float dx = x - ix, dy = y - iy, dz = z - iz;

    // Compute gradient weights
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

    // Compute trilinear interpolation of weights
    float wx = NoiseWeight(dx), wy = NoiseWeight(dy), wz = NoiseWeight(dz);
    float x00 = Lerp(wx, w000, w100);
    float x10 = Lerp(wx, w010, w110);
    float x01 = Lerp(wx, w001, w101);
    float x11 = Lerp(wx, w011, w111);
    float y0 = Lerp(wy, x00, x10);
    float y1 = Lerp(wy, x01, x11);
    return Lerp(wz, y0, y1);
}

static float Turbulence(float x, float y, float z, int octaves) {
    float omega = 0.6;

    float sum = 0., lambda = 1., o = 1.;
    for (int i = 0; i < octaves; ++i) {
        sum += fabsf(o * Noise(lambda * x, lambda * y, lambda * z));
        lambda *= 1.99f;
        o *= omega;
    }
    return sum * 0.5f;
}

static inline __m256 VGrad(__m256i x, __m256i y, __m256i z, __m256 dx, __m256 dy, __m256 dz)
    __attribute__((target("avx2"))) {
    const __m256i fifteen = _mm256_set1_epi32(15);
    const __m256i twelve = _mm256_set1_epi32(12);
    const __m256i thirteen = _mm256_set1_epi32(13);
    const __m256i eight = _mm256_set1_epi32(8);
    const __m256i four = _mm256_set1_epi32(4);
    const __m256i one = _mm256_set1_epi32(1);
    const __m256i two = _mm256_set1_epi32(2);
    const __m256 zero = _mm256_setzero_ps();

    __m256i h = _mm256_i32gather_epi32(NoisePerm,
        _mm256_add_epi32(_mm256_i32gather_epi32(NoisePerm,
            _mm256_add_epi32(_mm256_i32gather_epi32(NoisePerm, x, 4), y), 4), z), 4);
    h = _mm256_and_si256(h, fifteen);

    __m256i special = _mm256_or_si256(_mm256_cmpeq_epi32(h, twelve), _mm256_cmpeq_epi32(h, thirteen));
    __m256i use_dx = _mm256_or_si256(_mm256_cmpgt_epi32(eight, h), special);
    __m256i use_dy = _mm256_or_si256(_mm256_cmpgt_epi32(four, h), special);
    __m256 u = _mm256_blendv_ps(dy, dx, _mm256_castsi256_ps(use_dx));
    __m256 v = _mm256_blendv_ps(dz, dy, _mm256_castsi256_ps(use_dy));

    __m256i neg_u = _mm256_cmpeq_epi32(_mm256_and_si256(h, one), one);
    __m256i neg_v = _mm256_cmpeq_epi32(_mm256_and_si256(h, two), two);
    u = _mm256_blendv_ps(u, _mm256_sub_ps(zero, u), _mm256_castsi256_ps(neg_u));
    v = _mm256_blendv_ps(v, _mm256_sub_ps(zero, v), _mm256_castsi256_ps(neg_v));
    return _mm256_add_ps(u, v);
}

static inline __m256 VNoiseWeight(__m256 t) __attribute__((target("avx2"))) {
    __m256 t3 = _mm256_mul_ps(_mm256_mul_ps(t, t), t);
    __m256 t4 = _mm256_mul_ps(t3, t);
    __m256 first = _mm256_mul_ps(_mm256_mul_ps(_mm256_set1_ps(6.f), t4), t);
    __m256 second = _mm256_mul_ps(_mm256_set1_ps(15.f), t4);
    __m256 third = _mm256_mul_ps(_mm256_set1_ps(10.f), t3);
    return _mm256_add_ps(_mm256_sub_ps(first, second), third);
}

static inline __m256 VLerp(__m256 t, __m256 low, __m256 high) __attribute__((target("avx2"))) {
    __m256 one_minus_t = _mm256_sub_ps(_mm256_set1_ps(1.f), t);
    return _mm256_add_ps(_mm256_mul_ps(one_minus_t, low), _mm256_mul_ps(t, high));
}

static inline __m256 VNoise(__m256 x, __m256 y, __m256 z) __attribute__((target("avx2"))) {
    __m256i ix = _mm256_cvttps_epi32(_mm256_floor_ps(x));
    __m256i iy = _mm256_cvttps_epi32(_mm256_floor_ps(y));
    __m256i iz = _mm256_cvttps_epi32(_mm256_floor_ps(z));
    __m256 dx = _mm256_sub_ps(x, _mm256_cvtepi32_ps(ix));
    __m256 dy = _mm256_sub_ps(y, _mm256_cvtepi32_ps(iy));
    __m256 dz = _mm256_sub_ps(z, _mm256_cvtepi32_ps(iz));

    const __m256i mask = _mm256_set1_epi32(NOISE_PERM_SIZE - 1);
    ix = _mm256_and_si256(ix, mask);
    iy = _mm256_and_si256(iy, mask);
    iz = _mm256_and_si256(iz, mask);
    __m256i ix1 = _mm256_add_epi32(ix, _mm256_set1_epi32(1));
    __m256i iy1 = _mm256_add_epi32(iy, _mm256_set1_epi32(1));
    __m256i iz1 = _mm256_add_epi32(iz, _mm256_set1_epi32(1));
    __m256 dx1 = _mm256_sub_ps(dx, _mm256_set1_ps(1.f));
    __m256 dy1 = _mm256_sub_ps(dy, _mm256_set1_ps(1.f));
    __m256 dz1 = _mm256_sub_ps(dz, _mm256_set1_ps(1.f));

    __m256 w000 = VGrad(ix,  iy,  iz,  dx,  dy,  dz);
    __m256 w100 = VGrad(ix1, iy,  iz,  dx1, dy,  dz);
    __m256 w010 = VGrad(ix,  iy1, iz,  dx,  dy1, dz);
    __m256 w110 = VGrad(ix1, iy1, iz,  dx1, dy1, dz);
    __m256 w001 = VGrad(ix,  iy,  iz1, dx,  dy,  dz1);
    __m256 w101 = VGrad(ix1, iy,  iz1, dx1, dy,  dz1);
    __m256 w011 = VGrad(ix,  iy1, iz1, dx,  dy1, dz1);
    __m256 w111 = VGrad(ix1, iy1, iz1, dx1, dy1, dz1);

    __m256 wx = VNoiseWeight(dx), wy = VNoiseWeight(dy), wz = VNoiseWeight(dz);
    __m256 x00 = VLerp(wx, w000, w100);
    __m256 x10 = VLerp(wx, w010, w110);
    __m256 x01 = VLerp(wx, w001, w101);
    __m256 x11 = VLerp(wx, w011, w111);
    __m256 y0 = VLerp(wy, x00, x10);
    __m256 y1 = VLerp(wy, x01, x11);
    return VLerp(wz, y0, y1);
}

static inline __m256 VTurbulence(__m256 x, __m256 y, __m256 z, int octaves)
    __attribute__((target("avx2"))) {
    __m256 omega = _mm256_set1_ps(0.6);
    __m256 sum = _mm256_setzero_ps();
    __m256 lambda = _mm256_set1_ps(1.f);
    __m256 o = _mm256_set1_ps(1.f);
    const __m256 sign_bit = _mm256_set1_ps(-0.0f);

    for (int i = 0; i < octaves; ++i) {
        __m256 noise = VNoise(_mm256_mul_ps(lambda, x), _mm256_mul_ps(lambda, y), _mm256_mul_ps(lambda, z));
        __m256 weighted = _mm256_mul_ps(o, noise);
        __m256 absolute = _mm256_andnot_ps(sign_bit, weighted);
        sum = _mm256_add_ps(sum, absolute);
        lambda = _mm256_mul_ps(lambda, _mm256_set1_ps(1.99f));
        o = _mm256_mul_ps(o, omega);
    }
    return _mm256_mul_ps(sum, _mm256_set1_ps(0.5f));
}

static void noise_serial_avx2(float x0, float y0, float x1, float y1, int width, int height, float output[])
    __attribute__((target("avx2"))) {
    float dx = (x1 - x0) / width;
    float dy = (y1 - y0) / height;
    const __m256 dxv = _mm256_set1_ps(dx);
    const __m256 x0v = _mm256_set1_ps(x0);
    const __m256 z = _mm256_set1_ps(0.6f);
    const __m256i lane_offsets = _mm256_setr_epi32(0, 1, 2, 3, 4, 5, 6, 7);

    for (int j = 0; j < height; ++j) {
        float y = y0 + j * dy;
        __m256 yv = _mm256_set1_ps(y);
        int i = 0;
        for (; width - i >= 8; i += 8) {
            __m256i pixel_indices = _mm256_add_epi32(_mm256_set1_epi32(i), lane_offsets);
            __m256 x = _mm256_add_ps(x0v, _mm256_mul_ps(_mm256_cvtepi32_ps(pixel_indices), dxv));
            __m256 result = VTurbulence(x, yv, z, 8);
            _mm256_storeu_ps(output + j * width + i, result);
        }
        for (; i < width; ++i) {
            float x = x0 + i * dx;
            output[j * width + i] = Turbulence(x, y, 0.6f, 8);
        }
    }
}

void noise_serial(float x0, float y0, float x1, float y1, int width, int height, float output[]) {
    if (width >= 8) {
        noise_serial_avx2(x0, y0, x1, y1, width, height, output);
        return;
    }

    float dx = (x1 - x0) / width;
    float dy = (y1 - y0) / height;

    for (int j = 0; j < height; j++) {
        for (int i = 0; i < width; ++i) {
            float x = x0 + i * dx;
            float y = y0 + j * dy;

            int index = (j * width + i);
            output[index] = Turbulence(x, y, 0.6f, 8);
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