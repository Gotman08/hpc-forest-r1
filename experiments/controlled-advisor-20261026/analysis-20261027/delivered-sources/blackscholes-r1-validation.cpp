/*
  Copyright (c) 2010-2023, Intel Corporation

  SPDX-License-Identifier: BSD-3-Clause
*/

#ifdef _MSC_VER
#define _CRT_SECURE_NO_WARNINGS
#define NOMINMAX
#pragma warning(disable : 4244)
#pragma warning(disable : 4305)
#endif

/*
  Copyright (c) 2010-2023, Intel Corporation

  SPDX-License-Identifier: BSD-3-Clause
*/

#ifndef OPTIONS_DEFS_H
#define OPTIONS_DEFS_H 1

#define BINOMIAL_NUM 64

#endif // OPTIONS_DEFS_H

#include <algorithm>
#include <cstring>
#include <math.h>
#include <omp.h>

// Cumulative normal distribution function
static inline float CND(float X) {
    float L = fabsf(X);

    float k = 1.f / (1.f + 0.2316419f * L);
    float q = k * k;

    const float invSqrt2Pi = 0.39894228040f;
    float odd = fmaf(q, fmaf(q, 1.330274429f, 1.781477937f), 0.31938153f);
    float even = fmaf(q, -1.821255978f, -0.356563782f);
    float w = fmaf(q, even, k * odd);
    w *= invSqrt2Pi * expf(-L * L * .5f);

    if (X > 0.f)
        w = 1.f - w;
    return w;
}

static inline float black_scholes_one(float S, float X, float T, float r, float v) {
    float d1 = (logf(S / X) + (r + v * v * .5f) * T) / (v * sqrtf(T));
    float d2 = d1 - v * sqrtf(T);
    return S * CND(d1) - X * expf(-r * T) * CND(d2);
}

#if defined(__GNUC__) || defined(__clang__)
typedef float float32 __attribute__((vector_size(128)));

static inline float32 load32(const float* p) {
    float32 value;
    std::memcpy(&value, p, sizeof(value));
    return value;
}

static inline void store32(float* p, float32 value) {
    std::memcpy(p, &value, sizeof(value));
}

// Use vector arithmetic for the q-based CND polynomial; transcendental calls remain scalar.
static inline float32 CND32(float32 X) {
    float32 L;
    float32 positive;
#if defined(_OPENMP)
#pragma omp simd
#endif
    for (int lane = 0; lane < 32; ++lane) {
        const float x = X[lane];
        L[lane] = fabsf(x);
        positive[lane] = x > 0.f ? 1.f : 0.f;
    }

    float32 k = 1.f / (1.f + 0.2316419f * L);
    float32 q = k * k;

    float32 exponential;
#if defined(_OPENMP)
#pragma omp simd
#endif
    for (int lane = 0; lane < 32; ++lane)
        exponential[lane] = expf(-L[lane] * L[lane] * .5f);

    const float invSqrt2Pi = 0.39894228040f;
    float32 odd = 0.31938153f + 1.781477937f * q + 1.330274429f * q * q;
    float32 even = -0.356563782f - 1.821255978f * q;
    float32 w = k * (odd + k * even);
    w *= invSqrt2Pi * exponential;

    // A 0/1 lane mask preserves the strict X > 0 rule without a lane branch.
    w = positive * (1.f - w) + (1.f - positive) * w;
    return w;
}
#endif

void black_scholes_serial(float Sa[], float Xa[], float Ta[], float ra[], float va[], float result[], int count) {
    for (int i = 0; i < count; ++i) {
        float S = Sa[i], X = Xa[i];
        float T = Ta[i], r = ra[i];
        float v = va[i];

        float d1 = (logf(S / X) + (r + v * v * .5f) * T) / (v * sqrtf(T));
        float d2 = d1 - v * sqrtf(T);

        result[i] = S * CND(d1) - X * expf(-r * T) * CND(d2);
    }
}

void binomial_put_serial(float Sa[], float Xa[], float Ta[], float ra[], float va[], float result[], int count) {
    float V[BINOMIAL_NUM];

    for (int i = 0; i < count; ++i) {
        float S = Sa[i], X = Xa[i];
        float T = Ta[i], r = ra[i];
        float v = va[i];

        float dt = T / BINOMIAL_NUM;
        float u = expf(v * sqrtf(dt));
        float d = 1.f / u;
        float disc = expf(r * dt);
        float Pu = (disc - d) / (u - d);

        for (int j = 0; j < BINOMIAL_NUM; ++j) {
            float upow = powf(u, (float)(2 * j - BINOMIAL_NUM));
            V[j] = std::max(0.f, X - S * upow);
        }

        for (int j = BINOMIAL_NUM - 1; j >= 0; --j)
            for (int k = 0; k < j; ++k)
                V[k] = ((1 - Pu) * V[k] + Pu * V[k + 1]) / disc;

        result[i] = V[0];
    }
}

extern "C" void run(const void* input1, const void* input2, void* output, int n, int parameter, int threads) {
    if (n <= 0)
        return;

    float* a = (float*)input1;
    float* result = (float*)output;

    if (threads <= 1 || n <= 1) {
        black_scholes_serial(a, a + n, a + 2 * n, a + 3 * n, a + 4 * n, result, n);
        return;
    }

    // Cap the OpenMP team at the caller's budget and the amount of work.
    const int team_size = std::min(threads, n);
    const int block_count = n / 32 + (n % 32 != 0);

    #pragma omp parallel for schedule(static) num_threads(team_size)
    for (int block = 0; block < block_count; ++block) {
        const int i = block * 32;
        const int remaining = n - i;

#if defined(__GNUC__) || defined(__clang__)
        if (remaining >= 32) {
            // Independent memcpy accesses allow different offsets and unaligned arrays.
            const float32 S = load32(a + i);
            const float32 X = load32(a + n + i);
            const float32 T = load32(a + 2 * n + i);
            const float32 r = load32(a + 3 * n + i);
            const float32 v = load32(a + 4 * n + i);

            const float32 ratio = S / X;
            float32 logRatio;
            float32 sqrtT;
            float32 discount;
#if defined(_OPENMP)
#pragma omp simd
#endif
            for (int lane = 0; lane < 32; ++lane) {
                logRatio[lane] = logf(ratio[lane]);
                sqrtT[lane] = sqrtf(T[lane]);
                discount[lane] = expf(-r[lane] * T[lane]);
            }

            const float32 vSqrtT = v * sqrtT;
            const float32 d1 = (logRatio + (r + v * v * .5f) * T) / vSqrtT;
            const float32 d2 = d1 - vSqrtT;
            const float32 value = S * CND32(d1) - X * discount * CND32(d2);
            store32(result + i, value);
            continue;
        }
#endif

        for (int lane = 0; lane < remaining && lane < 32; ++lane) {
            const int j = i + lane;
            result[j] = black_scholes_one(a[j], a[n + j], a[2 * n + j], a[3 * n + j], a[4 * n + j]);
        }
    }
}
