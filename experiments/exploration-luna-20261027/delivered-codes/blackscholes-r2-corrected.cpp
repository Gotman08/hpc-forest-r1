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

static constexpr float cnd0 = 0.31938153f * 0.39894228040f;
static constexpr float cnd1 = -0.356563782f * 0.39894228040f;
static constexpr float cnd2 = 1.781477937f * 0.39894228040f;
static constexpr float cnd3 = -1.821255978f * 0.39894228040f;
static constexpr float cnd4 = 1.330274429f * 0.39894228040f;

// Cumulative normal distribution function
static inline float CND(float X) {
    float L = fabsf(X);

    float k = 1.f / (1.f + 0.2316419f * L);
    float polynomial = cnd0 + k * (cnd1 + k * (cnd2 + k * (cnd3 + k * cnd4)));
    float w = k * polynomial;
    w *= expf(-L * L * .5f);

    if (X > 0.f)
        w = 1.f - w;
    return w;
}

#if defined(__GNUC__) || defined(__clang__)
// Explicit four-lane arithmetic; transcendental functions remain scalar.
typedef float bs_float4 __attribute__((vector_size(16)));

static inline bs_float4 CND4(bs_float4 X) {
    bs_float4 L = {fabsf(X[0]), fabsf(X[1]), fabsf(X[2]), fabsf(X[3])};
    const bs_float4 one = {1.f, 1.f, 1.f, 1.f};
    const bs_float4 c0 = {0.2316419f, 0.2316419f, 0.2316419f, 0.2316419f};
    const bs_float4 h0 = {cnd0, cnd0, cnd0, cnd0};
    const bs_float4 h1 = {cnd1, cnd1, cnd1, cnd1};
    const bs_float4 h2 = {cnd2, cnd2, cnd2, cnd2};
    const bs_float4 h3 = {cnd3, cnd3, cnd3, cnd3};
    const bs_float4 h4 = {cnd4, cnd4, cnd4, cnd4};

    bs_float4 k = one / (one + c0 * L);
    bs_float4 polynomial = h0 + k * (h1 + k * (h2 + k * (h3 + k * h4)));
    bs_float4 w = k * polynomial;
    bs_float4 exponential = {
        expf(-L[0] * L[0] * 0.5f),
        expf(-L[1] * L[1] * 0.5f),
        expf(-L[2] * L[2] * 0.5f),
        expf(-L[3] * L[3] * 0.5f)
    };
    w *= exponential;

    bs_float4 result;
    result[0] = X[0] > 0.f ? 1.f - w[0] : w[0];
    result[1] = X[1] > 0.f ? 1.f - w[1] : w[1];
    result[2] = X[2] > 0.f ? 1.f - w[2] : w[2];
    result[3] = X[3] > 0.f ? 1.f - w[3] : w[3];
    return result;
}

static inline void black_scholes_block4(float Sa[], float Xa[], float Ta[], float ra[], float va[], float result[], int i) {
    const bs_float4 half = {0.5f, 0.5f, 0.5f, 0.5f};
    bs_float4 S, X, T, r, v;
    // Per-array offsets and the output pointer need not retain 64-byte alignment.
    std::memcpy(&S, Sa + i, sizeof(S));
    std::memcpy(&X, Xa + i, sizeof(X));
    std::memcpy(&T, Ta + i, sizeof(T));
    std::memcpy(&r, ra + i, sizeof(r));
    std::memcpy(&v, va + i, sizeof(v));

    bs_float4 sqrtT = {sqrtf(T[0]), sqrtf(T[1]), sqrtf(T[2]), sqrtf(T[3])};
    bs_float4 logRatio = {
        logf(S[0] / X[0]), logf(S[1] / X[1]),
        logf(S[2] / X[2]), logf(S[3] / X[3])
    };
    bs_float4 volRootT = v * sqrtT;
    bs_float4 d1 = (logRatio + (r + v * v * half) * T) / volRootT;
    bs_float4 d2 = d1 - volRootT;
    bs_float4 discount = {
        expf(-r[0] * T[0]), expf(-r[1] * T[1]),
        expf(-r[2] * T[2]), expf(-r[3] * T[3])
    };
    bs_float4 price = S * CND4(d1) - X * discount * CND4(d2);
    std::memcpy(result + i, &price, sizeof(price));
}
#endif

static inline float black_scholes_one(float S, float X, float T, float r, float v) {
    float sqrtT = sqrtf(T);
    float volRootT = v * sqrtT;
    float d1 = (logf(S / X) + (r + v * v * .5f) * T) / volRootT;
    float d2 = d1 - volRootT;
    return S * CND(d1) - X * expf(-r * T) * CND(d2);
}

void black_scholes_simd(float Sa[], float Xa[], float Ta[], float ra[], float va[], float result[], int count, int threads) {
#if defined(__GNUC__) || defined(__clang__)
    const int vector_end = count > 0 ? count - count % 4 : 0;
    const int group_count = vector_end / 4;

    if (group_count > 0) {
        int workers = threads > 0 ? threads : 1;
        if (workers > group_count)
            workers = group_count;

        // Static contiguous chunks test whether uniform block costs avoid guided dispatch overhead.
        #pragma omp parallel for schedule(static) num_threads(workers)
        for (int group = 0; group < group_count; ++group)
            black_scholes_block4(Sa, Xa, Ta, ra, va, result, group * 4);
    }

    // The parallel vector loop ends before the at-most-three scalar tail elements.
    for (int i = vector_end; i < count; ++i)
        result[i] = black_scholes_one(Sa[i], Xa[i], Ta[i], ra[i], va[i]);
#else
    int workers = threads > 0 ? threads : 1;
    if (count > 0 && workers > count)
        workers = count;

    #pragma omp parallel for schedule(guided, 8) num_threads(workers)
    for (int i = 0; i < count; ++i)
        result[i] = black_scholes_one(Sa[i], Xa[i], Ta[i], ra[i], va[i]);
#endif
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
#include <cstdint>
#include <cstring>
#include <cmath>
#include <algorithm>
#include <omp.h>
extern "C" void run(const void* input1,const void* input2,void* output,int n,int parameter,int threads)
{float*a=(float*)input1;black_scholes_simd(a,a+n,a+2*n,a+3*n,a+4*n,(float*)output,n,threads);}
