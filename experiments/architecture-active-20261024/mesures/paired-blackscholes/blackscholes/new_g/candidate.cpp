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

    const float invSqrt2Pi = 0.39894228040f;
    float w = k * (0.31938153f + k * (-0.356563782f + k * (1.781477937f + k * (-1.821255978f + k * 1.330274429f))));
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

void black_scholes_serial(const float Sa[], const float Xa[], const float Ta[],
                          const float ra[], const float va[], float result[], int count) {
    for (int i = 0; i < count; ++i)
        result[i] = black_scholes_option(Sa[i], Xa[i], Ta[i], ra[i], va[i]);
}

#if defined(__SSE2__) || defined(_M_X64) || (defined(_M_IX86_FP) && _M_IX86_FP >= 2)
static inline bool black_scholes_sse2_positive_normal(__m128 x) {
    const __m128i bits = _mm_castps_si128(x);
    const __m128i zero = _mm_setzero_si128();
    const __m128i exponent = _mm_and_si128(_mm_srli_epi32(bits, 23), _mm_set1_epi32(0xff));
    const __m128i positive = _mm_cmpeq_epi32(_mm_srai_epi32(bits, 31), zero);
    const __m128i normal = _mm_and_si128(
        _mm_cmpgt_epi32(exponent, zero),
        _mm_cmpgt_epi32(_mm_set1_epi32(0xff), exponent));
    const __m128i valid = _mm_and_si128(positive, normal);
    return _mm_movemask_ps(_mm_castsi128_ps(valid)) == 0xf;
}

static inline bool black_scholes_sse2_in_range(__m128 x, float low, float high) {
    const __m128 valid = _mm_and_ps(
        _mm_cmpge_ps(x, _mm_set1_ps(low)),
        _mm_cmple_ps(x, _mm_set1_ps(high)));
    return _mm_movemask_ps(valid) == 0xf;
}

// Approximate log(x) for positive normal lanes; callers check this domain first.
static inline __m128 black_scholes_log_sse2(__m128 x) {
    const __m128 one = _mm_set1_ps(1.f);
    const __m128i bits = _mm_castps_si128(x);
    __m128i exponent = _mm_sub_epi32(
        _mm_and_si128(_mm_srli_epi32(bits, 23), _mm_set1_epi32(0xff)),
        _mm_set1_epi32(127));
    const __m128i mantissaBits = _mm_or_si128(
        _mm_and_si128(bits, _mm_set1_epi32(0x007fffff)),
        _mm_set1_epi32(0x3f800000));
    __m128 mantissa = _mm_castsi128_ps(mantissaBits);

    const __m128 adjust = _mm_cmpgt_ps(mantissa, _mm_set1_ps(1.41421356237f));
    mantissa = _mm_or_ps(
        _mm_and_ps(adjust, _mm_mul_ps(mantissa, _mm_set1_ps(0.5f))),
        _mm_andnot_ps(adjust, mantissa));
    exponent = _mm_add_epi32(
        exponent,
        _mm_and_si128(_mm_castps_si128(adjust), _mm_set1_epi32(1)));

    const __m128 y = _mm_div_ps(_mm_sub_ps(mantissa, one), _mm_add_ps(mantissa, one));
    const __m128 y2 = _mm_mul_ps(y, y);
    __m128 polynomial = _mm_set1_ps(1.f / 13.f);
    polynomial = _mm_add_ps(_mm_set1_ps(1.f / 11.f), _mm_mul_ps(y2, polynomial));
    polynomial = _mm_add_ps(_mm_set1_ps(1.f / 9.f), _mm_mul_ps(y2, polynomial));
    polynomial = _mm_add_ps(_mm_set1_ps(1.f / 7.f), _mm_mul_ps(y2, polynomial));
    polynomial = _mm_add_ps(_mm_set1_ps(1.f / 5.f), _mm_mul_ps(y2, polynomial));
    polynomial = _mm_add_ps(_mm_set1_ps(1.f / 3.f), _mm_mul_ps(y2, polynomial));
    polynomial = _mm_add_ps(one, _mm_mul_ps(y2, polynomial));

    const __m128 logMantissa = _mm_mul_ps(_mm_set1_ps(2.f), _mm_mul_ps(y, polynomial));
    const __m128 logExponent = _mm_mul_ps(
        _mm_cvtepi32_ps(exponent), _mm_set1_ps(0.6931471805599453f));
    return _mm_add_ps(logExponent, logMantissa);
}

// Approximate exp(x) on [-80, 80]; callers check this domain first.
static inline __m128 black_scholes_exp_sse2(__m128 x) {
    const __m128 zero = _mm_setzero_ps();
    const __m128 q = _mm_mul_ps(x, _mm_set1_ps(1.4426950408889634f));
    const __m128 adjustment = _mm_or_ps(
        _mm_and_ps(_mm_cmpgt_ps(zero, q), _mm_set1_ps(-0.5f)),
        _mm_andnot_ps(_mm_cmpgt_ps(zero, q), _mm_set1_ps(0.5f)));
    const __m128i exponent = _mm_cvttps_epi32(_mm_add_ps(q, adjustment));
    const __m128 exponentFloat = _mm_cvtepi32_ps(exponent);

    __m128 remainder = _mm_sub_ps(
        x, _mm_mul_ps(exponentFloat, _mm_set1_ps(0.693145751953125f)));
    remainder = _mm_sub_ps(
        remainder, _mm_mul_ps(exponentFloat, _mm_set1_ps(1.428606765330187e-6f)));

    __m128 polynomial = _mm_set1_ps(1.f / 40320.f);
    polynomial = _mm_add_ps(_mm_set1_ps(1.f / 5040.f), _mm_mul_ps(remainder, polynomial));
    polynomial = _mm_add_ps(_mm_set1_ps(1.f / 720.f), _mm_mul_ps(remainder, polynomial));
    polynomial = _mm_add_ps(_mm_set1_ps(1.f / 120.f), _mm_mul_ps(remainder, polynomial));
    polynomial = _mm_add_ps(_mm_set1_ps(1.f / 24.f), _mm_mul_ps(remainder, polynomial));
    polynomial = _mm_add_ps(_mm_set1_ps(1.f / 6.f), _mm_mul_ps(remainder, polynomial));
    polynomial = _mm_add_ps(_mm_set1_ps(0.5f), _mm_mul_ps(remainder, polynomial));
    polynomial = _mm_add_ps(_mm_set1_ps(1.f), _mm_mul_ps(remainder, polynomial));
    polynomial = _mm_add_ps(_mm_set1_ps(1.f), _mm_mul_ps(remainder, polynomial));

    const __m128i scaleBits = _mm_slli_epi32(
        _mm_add_epi32(exponent, _mm_set1_epi32(127)), 23);
    return _mm_mul_ps(polynomial, _mm_castsi128_ps(scaleBits));
}

static inline __m128 black_scholes_cnd_sse2(__m128 x) {
    const __m128 zero = _mm_setzero_ps();
    const __m128 one = _mm_set1_ps(1.f);
    const __m128 absMask = _mm_castsi128_ps(_mm_set1_epi32(0x7fffffff));
    const __m128 L = _mm_and_ps(x, absMask);

    const __m128 k = _mm_div_ps(one, _mm_add_ps(one, _mm_mul_ps(_mm_set1_ps(0.2316419f), L)));
    __m128 w = _mm_set1_ps(1.330274429f);
    w = _mm_add_ps(_mm_set1_ps(-1.821255978f), _mm_mul_ps(k, w));
    w = _mm_add_ps(_mm_set1_ps(1.781477937f), _mm_mul_ps(k, w));
    w = _mm_add_ps(_mm_set1_ps(-0.356563782f), _mm_mul_ps(k, w));
    w = _mm_add_ps(_mm_set1_ps(0.31938153f), _mm_mul_ps(k, w));
    w = _mm_mul_ps(k, w);

    const __m128 expArgument = _mm_mul_ps(_mm_mul_ps(_mm_sub_ps(zero, L), L), _mm_set1_ps(.5f));
    const __m128 scale = _mm_mul_ps(_mm_set1_ps(0.39894228040f), black_scholes_exp_sse2(expArgument));
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
    const __m128 S = _mm_loadu_ps(Sa + i);
    const __m128 X = _mm_loadu_ps(Xa + i);
    const __m128 T = _mm_loadu_ps(Ta + i);
    const __m128 r = _mm_loadu_ps(ra + i);
    const __m128 v = _mm_loadu_ps(va + i);
    const __m128 ratio = _mm_div_ps(S, X);

    if (!black_scholes_sse2_positive_normal(ratio)) {
        black_scholes_serial(Sa + i, Xa + i, Ta + i, ra + i, va + i, result + i, 4);
        return;
    }

    const __m128 logRatio = black_scholes_log_sse2(ratio);
    const __m128 rootT = _mm_sqrt_ps(T);
    const __m128 numerator = _mm_add_ps(
        logRatio,
        _mm_mul_ps(_mm_add_ps(r, _mm_mul_ps(_mm_mul_ps(v, v), half)), T));
    const __m128 vRootT = _mm_mul_ps(v, rootT);
    const __m128 d1 = _mm_div_ps(numerator, vRootT);
    const __m128 d2 = _mm_sub_ps(d1, vRootT);

    const __m128 absD1 = _mm_and_ps(d1, _mm_castsi128_ps(_mm_set1_epi32(0x7fffffff)));
    const __m128 absD2 = _mm_and_ps(d2, _mm_castsi128_ps(_mm_set1_epi32(0x7fffffff)));
    const __m128 cndExp1 = _mm_mul_ps(_mm_mul_ps(_mm_sub_ps(zero, absD1), absD1), half);
    const __m128 cndExp2 = _mm_mul_ps(_mm_mul_ps(_mm_sub_ps(zero, absD2), absD2), half);
    const __m128 discountArgument = _mm_mul_ps(_mm_sub_ps(zero, r), T);
    if (!black_scholes_sse2_in_range(cndExp1, -80.f, 0.f) ||
        !black_scholes_sse2_in_range(cndExp2, -80.f, 0.f) ||
        !black_scholes_sse2_in_range(discountArgument, -80.f, 80.f)) {
        black_scholes_serial(Sa + i, Xa + i, Ta + i, ra + i, va + i, result + i, 4);
        return;
    }

    const __m128 cnd1 = black_scholes_cnd_sse2(d1);
    const __m128 cnd2 = black_scholes_cnd_sse2(d2);
    const __m128 discountedStrike = _mm_mul_ps(X, black_scholes_exp_sse2(discountArgument));
    const __m128 optionValue = _mm_sub_ps(
        _mm_mul_ps(S, cnd1), _mm_mul_ps(discountedStrike, cnd2));
    _mm_storeu_ps(result + i, optionValue);
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
