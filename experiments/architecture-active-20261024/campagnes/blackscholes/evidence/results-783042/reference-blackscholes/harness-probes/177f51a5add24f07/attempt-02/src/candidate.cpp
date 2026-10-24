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

#if defined(__SSE2__) || defined(_M_X64) || (defined(_M_IX86_FP) && _M_IX86_FP >= 2)
static inline bool black_scholes_sse2_in_range(__m128 x, float low, float high) {
    const __m128 valid = _mm_and_ps(
        _mm_cmpge_ps(x, _mm_set1_ps(low)),
        _mm_cmple_ps(x, _mm_set1_ps(high)));
    return _mm_movemask_ps(valid) == 0xf;
}

// Approximate exp(x) for x in [-80, 0]; callers check this domain first.
static inline __m128 black_scholes_cnd_exp_sse2(__m128 x) {
    const __m128 zero = _mm_setzero_ps();
    const __m128 q = _mm_mul_ps(x, _mm_set1_ps(1.4426950408889634f));
    const __m128 negative = _mm_cmpgt_ps(zero, q);
    const __m128 adjustment = _mm_or_ps(
        _mm_and_ps(negative, _mm_set1_ps(-0.5f)),
        _mm_andnot_ps(negative, _mm_set1_ps(0.5f)));
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
    const __m128 half = _mm_set1_ps(0.5f);
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

    const __m128 expArgument = _mm_mul_ps(_mm_mul_ps(_mm_sub_ps(zero, L), L), half);
    const __m128 scale = _mm_mul_ps(
        _mm_set1_ps(0.39894228040f), black_scholes_cnd_exp_sse2(expArgument));
    w = _mm_mul_ps(w, scale);

    const __m128 positive = _mm_cmpgt_ps(x, zero);
    const __m128 oneMinusW = _mm_sub_ps(one, w);
    return _mm_or_ps(_mm_and_ps(positive, oneMinusW), _mm_andnot_ps(positive, w));
}
#endif

static inline void black_scholes_explicit(float Sa[], float Xa[], float Ta[], float ra[], float va[], float result[], int count) {
#if defined(__SSE2__) || defined(_M_X64) || (defined(_M_IX86_FP) && _M_IX86_FP >= 2)
    int i = 0;
    const __m128 zero = _mm_setzero_ps();
    const __m128 half = _mm_set1_ps(0.5f);

    for (; count - i >= 4; i += 4) {
        const __m128 S = _mm_loadu_ps(Sa + i);
        const __m128 X = _mm_loadu_ps(Xa + i);
        float d1Values[4];
        float d2Values[4];
        float discountValues[4];

        for (int lane = 0; lane < 4; ++lane) {
            const float spot = Sa[i + lane];
            const float strike = Xa[i + lane];
            const float time = Ta[i + lane];
            const float rate = ra[i + lane];
            const float volatility = va[i + lane];
            const float rootT = sqrtf(time);
            const float vRootT = volatility * rootT;
            d1Values[lane] =
                (logf(spot / strike) + (rate + volatility * volatility * 0.5f) * time) / vRootT;
            d2Values[lane] = d1Values[lane] - vRootT;
            discountValues[lane] = expf(-rate * time);
        }

        const __m128 d1 = _mm_loadu_ps(d1Values);
        const __m128 d2 = _mm_loadu_ps(d2Values);
        const __m128 absMask = _mm_castsi128_ps(_mm_set1_epi32(0x7fffffff));
        const __m128 absD1 = _mm_and_ps(d1, absMask);
        const __m128 absD2 = _mm_and_ps(d2, absMask);
        const __m128 cndExp1 = _mm_mul_ps(_mm_mul_ps(_mm_sub_ps(zero, absD1), absD1), half);
        const __m128 cndExp2 = _mm_mul_ps(_mm_mul_ps(_mm_sub_ps(zero, absD2), absD2), half);

        if (!black_scholes_sse2_in_range(cndExp1, -80.f, 0.f) ||
            !black_scholes_sse2_in_range(cndExp2, -80.f, 0.f)) {
            black_scholes_serial(Sa + i, Xa + i, Ta + i, ra + i, va + i, result + i, 4);
            continue;
        }

        const __m128 cnd1 = black_scholes_cnd_sse2(d1);
        const __m128 cnd2 = black_scholes_cnd_sse2(d2);
        const __m128 discount = _mm_loadu_ps(discountValues);
        const __m128 discountedStrike = _mm_mul_ps(X, discount);
        const __m128 optionValue = _mm_sub_ps(
            _mm_mul_ps(S, cnd1), _mm_mul_ps(discountedStrike, cnd2));
        _mm_storeu_ps(result + i, optionValue);
    }

    if (i < count)
        black_scholes_serial(Sa + i, Xa + i, Ta + i, ra + i, va + i, result + i, count - i);
#else
    black_scholes_serial(Sa, Xa, Ta, ra, va, result, count);
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
{float*a=(float*)input1;black_scholes_explicit(a,a+n,a+2*n,a+3*n,a+4*n,(float*)output,n);}
