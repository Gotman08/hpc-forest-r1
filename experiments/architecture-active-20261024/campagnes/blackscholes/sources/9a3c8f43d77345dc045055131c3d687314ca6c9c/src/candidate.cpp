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
#include <math.h>

#if defined(__SSE2__) || defined(_M_X64) || (defined(_M_IX86_FP) && _M_IX86_FP >= 2)
#include <emmintrin.h>
#endif

#include <cstdint>
#include <cstring>
#include <cmath>
#include <omp.h>

// Cumulative normal distribution function
static inline float CND(float X) {
    float L = fabsf(X);

    float k = 1.f / (1.f + 0.2316419f * L);
    float k2 = k * k;
    float k3 = k2 * k;
    float k4 = k2 * k2;
    float k5 = k3 * k2;

    const float invSqrt2Pi = 0.39894228040f;
    float w = (0.31938153f * k - 0.356563782f * k2 + 1.781477937f * k3 + -1.821255978f * k4 + 1.330274429f * k5);
    w *= invSqrt2Pi * expf(-L * L * .5f);

    if (X > 0.f)
        w = 1.f - w;
    return w;
}

static inline float black_scholes_option(float S, float X, float T, float r, float v) {
    float d1 = (logf(S / X) + (r + v * v * .5f) * T) / (v * sqrtf(T));
    float d2 = d1 - v * sqrtf(T);
    return S * CND(d1) - X * expf(-r * T) * CND(d2);
}

void black_scholes_serial(float Sa[], float Xa[], float Ta[], float ra[], float va[], float result[], int count) {
    for (int i = 0; i < count; ++i)
        result[i] = black_scholes_option(Sa[i], Xa[i], Ta[i], ra[i], va[i]);
}

#if defined(__SSE2__) || defined(_M_X64) || (defined(_M_IX86_FP) && _M_IX86_FP >= 2)
static inline __m128 black_scholes_cnd_sse2(__m128 x) {
    const __m128 zero = _mm_setzero_ps();
    const __m128 one = _mm_set1_ps(1.f);
    const __m128 absMask = _mm_castsi128_ps(_mm_set1_epi32(0x7fffffff));
    const __m128 L = _mm_and_ps(x, absMask);

    const __m128 k = _mm_div_ps(one, _mm_add_ps(one, _mm_mul_ps(_mm_set1_ps(0.2316419f), L)));
    const __m128 k2 = _mm_mul_ps(k, k);
    const __m128 k3 = _mm_mul_ps(k2, k);
    const __m128 k4 = _mm_mul_ps(k2, k2);
    const __m128 k5 = _mm_mul_ps(k3, k2);

    __m128 w = _mm_sub_ps(_mm_mul_ps(_mm_set1_ps(0.31938153f), k),
                          _mm_mul_ps(_mm_set1_ps(0.356563782f), k2));
    w = _mm_add_ps(w, _mm_mul_ps(_mm_set1_ps(1.781477937f), k3));
    w = _mm_add_ps(w, _mm_mul_ps(_mm_set1_ps(-1.821255978f), k4));
    w = _mm_add_ps(w, _mm_mul_ps(_mm_set1_ps(1.330274429f), k5));

    float expArguments[4];
    float expValues[4];
    const __m128 expArgument = _mm_mul_ps(_mm_mul_ps(_mm_sub_ps(zero, L), L), _mm_set1_ps(.5f));
    _mm_storeu_ps(expArguments, expArgument);
    for (int lane = 0; lane < 4; ++lane)
        expValues[lane] = expf(expArguments[lane]);

    const __m128 scale = _mm_mul_ps(_mm_set1_ps(0.39894228040f), _mm_loadu_ps(expValues));
    w = _mm_mul_ps(w, scale);

    const __m128 positive = _mm_cmpgt_ps(x, zero);
    const __m128 oneMinusW = _mm_sub_ps(one, w);
    return _mm_or_ps(_mm_and_ps(positive, oneMinusW), _mm_andnot_ps(positive, w));
}

static inline void black_scholes_four_sse2(const float* Sa, const float* Xa,
                                            const float* Ta, const float* ra,
                                            const float* va, float* result, int i) {
    const __m128 zero = _mm_setzero_ps();
    const __m128 half = _mm_set1_ps(.5f);
    const __m128 s = _mm_loadu_ps(Sa + i);
    const __m128 x = _mm_loadu_ps(Xa + i);
    const __m128 t = _mm_loadu_ps(Ta + i);
    const __m128 r = _mm_loadu_ps(ra + i);
    const __m128 v = _mm_loadu_ps(va + i);

    float ratios[4];
    float logValues[4];
    const __m128 ratio = _mm_div_ps(s, x);
    _mm_storeu_ps(ratios, ratio);
    for (int lane = 0; lane < 4; ++lane)
        logValues[lane] = logf(ratios[lane]);

    const __m128 sqrtT = _mm_sqrt_ps(t);
    const __m128 vSquaredHalf = _mm_mul_ps(_mm_mul_ps(v, v), half);
    const __m128 drift = _mm_mul_ps(_mm_add_ps(r, vSquaredHalf), t);
    const __m128 numerator = _mm_add_ps(_mm_loadu_ps(logValues), drift);
    const __m128 denominator = _mm_mul_ps(v, sqrtT);
    const __m128 d1 = _mm_div_ps(numerator, denominator);
    const __m128 d2 = _mm_sub_ps(d1, _mm_mul_ps(v, sqrtT));

    float discountArguments[4];
    float discountValues[4];
    const __m128 discountArgument = _mm_mul_ps(_mm_sub_ps(zero, r), t);
    _mm_storeu_ps(discountArguments, discountArgument);
    for (int lane = 0; lane < 4; ++lane)
        discountValues[lane] = expf(discountArguments[lane]);

    const __m128 cnd1 = black_scholes_cnd_sse2(d1);
    const __m128 cnd2 = black_scholes_cnd_sse2(d2);
    const __m128 discountedStrike = _mm_mul_ps(_mm_mul_ps(x, _mm_loadu_ps(discountValues)), cnd2);
    const __m128 price = _mm_sub_ps(_mm_mul_ps(s, cnd1), discountedStrike);
    _mm_storeu_ps(result + i, price);
}
#endif

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

extern "C" void run(const void* input1, const void* input2, void* output,
                    int n, int parameter, int threads) {
    float* a = (float*)input1;
    float* result = (float*)output;

    if (n <= 0)
        return;

    if (threads <= 1) {
        black_scholes_serial(a, a + n, a + 2 * n, a + 3 * n, a + 4 * n, result, n);
        return;
    }

    const int team_size = threads < n ? threads : n;
    if (team_size <= 1 || n / team_size < 256) {
        black_scholes_serial(a, a + n, a + 2 * n, a + 3 * n, a + 4 * n, result, n);
        return;
    }

#if defined(__SSE2__) || defined(_M_X64) || (defined(_M_IX86_FP) && _M_IX86_FP >= 2)
    const int vector_blocks = n / 4;
#pragma omp parallel for schedule(static) num_threads(team_size)
    for (int block = 0; block < vector_blocks; ++block)
        black_scholes_four_sse2(a, a + n, a + 2 * n, a + 3 * n, a + 4 * n,
                                result, block * 4);

    for (int i = vector_blocks * 4; i < n; ++i)
        result[i] = black_scholes_option(a[i], a[n + i], a[2 * n + i], a[3 * n + i], a[4 * n + i]);
#else
#pragma omp parallel for schedule(static) num_threads(team_size)
    for (int i = 0; i < n; ++i)
        result[i] = black_scholes_option(a[i], a[n + i], a[2 * n + i], a[3 * n + i], a[4 * n + i]);
#endif
}
