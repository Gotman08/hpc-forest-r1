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
static inline bool black_scholes_sse2_finite(__m128 value) {
    const __m128 absMask = _mm_castsi128_ps(_mm_set1_epi32(0x7fffffff));
    const __m128 infinity = _mm_set1_ps(INFINITY);
    const __m128 magnitude = _mm_and_ps(value, absMask);
    return _mm_movemask_ps(_mm_cmplt_ps(magnitude, infinity)) == 0xF;
}

static inline bool black_scholes_sse2_positive_normal(__m128 value) {
    const __m128 minNormal = _mm_set1_ps(1.17549435e-38f);
    const __m128 infinity = _mm_set1_ps(INFINITY);
    return _mm_movemask_ps(_mm_cmpge_ps(value, minNormal)) == 0xF &&
           _mm_movemask_ps(_mm_cmplt_ps(value, infinity)) == 0xF;
}

static inline bool black_scholes_sse2_nonzero_normal(__m128 value) {
    const __m128 absMask = _mm_castsi128_ps(_mm_set1_epi32(0x7fffffff));
    const __m128 minNormal = _mm_set1_ps(1.17549435e-38f);
    const __m128 infinity = _mm_set1_ps(INFINITY);
    const __m128 magnitude = _mm_and_ps(value, absMask);
    return _mm_movemask_ps(_mm_cmpge_ps(magnitude, minNormal)) == 0xF &&
           _mm_movemask_ps(_mm_cmplt_ps(magnitude, infinity)) == 0xF;
}

static inline bool black_scholes_sse2_safe_exp_argument(__m128 value) {
    const __m128 lower = _mm_set1_ps(-80.f);
    const __m128 upper = _mm_set1_ps(80.f);
    return black_scholes_sse2_finite(value) &&
           _mm_movemask_ps(_mm_cmpge_ps(value, lower)) == 0xF &&
           _mm_movemask_ps(_mm_cmple_ps(value, upper)) == 0xF;
}

static inline __m128 black_scholes_log_sse2(__m128 value) {
    const __m128 one = _mm_set1_ps(1.f);
    const __m128 two = _mm_set1_ps(2.f);
    const __m128i exponentBits = _mm_and_si128(
        _mm_srli_epi32(_mm_castps_si128(value), 23), _mm_set1_epi32(0xff));
    const __m128i exponentInt = _mm_sub_epi32(exponentBits, _mm_set1_epi32(127));
    const __m128 exponent = _mm_cvtepi32_ps(exponentInt);
    const __m128 mantissa = _mm_castsi128_ps(_mm_or_si128(
        _mm_and_si128(_mm_castps_si128(value), _mm_set1_epi32(0x007fffff)),
        _mm_set1_epi32(0x3f800000)));

    const __m128 y = _mm_div_ps(_mm_sub_ps(mantissa, one), _mm_add_ps(mantissa, one));
    const __m128 z = _mm_mul_ps(y, y);
    __m128 polynomial = _mm_set1_ps(1.f / 15.f);
    polynomial = _mm_add_ps(_mm_set1_ps(1.f / 13.f), _mm_mul_ps(z, polynomial));
    polynomial = _mm_add_ps(_mm_set1_ps(1.f / 11.f), _mm_mul_ps(z, polynomial));
    polynomial = _mm_add_ps(_mm_set1_ps(1.f / 9.f), _mm_mul_ps(z, polynomial));
    polynomial = _mm_add_ps(_mm_set1_ps(1.f / 7.f), _mm_mul_ps(z, polynomial));
    polynomial = _mm_add_ps(_mm_set1_ps(1.f / 5.f), _mm_mul_ps(z, polynomial));
    polynomial = _mm_add_ps(_mm_set1_ps(1.f / 3.f), _mm_mul_ps(z, polynomial));
    polynomial = _mm_add_ps(one, _mm_mul_ps(z, polynomial));
    const __m128 logMantissa = _mm_mul_ps(_mm_mul_ps(two, y), polynomial);

    const __m128 high = _mm_add_ps(
        _mm_mul_ps(exponent, _mm_set1_ps(0.693359375f)), logMantissa);
    return _mm_add_ps(high, _mm_mul_ps(exponent, _mm_set1_ps(-0.00021219444005469058f)));
}

static inline __m128 black_scholes_exp_sse2(__m128 value) {
    const __m128 zero = _mm_setzero_ps();
    const __m128 negative = _mm_cmplt_ps(value, zero);
    const __m128 adjustment = _mm_or_ps(
        _mm_and_ps(negative, _mm_set1_ps(-0.5f)),
        _mm_andnot_ps(negative, _mm_set1_ps(0.5f)));
    const __m128 scaled = _mm_mul_ps(value, _mm_set1_ps(1.4426950408889634f));
    const __m128i exponent = _mm_cvttps_epi32(_mm_add_ps(scaled, adjustment));
    const __m128 exponentFloat = _mm_cvtepi32_ps(exponent);
    const __m128 reduced = _mm_sub_ps(
        _mm_sub_ps(value, _mm_mul_ps(exponentFloat, _mm_set1_ps(0.693359375f))),
        _mm_mul_ps(exponentFloat, _mm_set1_ps(-0.00021219444005469058f)));

    __m128 polynomial = _mm_set1_ps(1.f / 40320.f);
    polynomial = _mm_add_ps(_mm_set1_ps(1.f / 5040.f), _mm_mul_ps(reduced, polynomial));
    polynomial = _mm_add_ps(_mm_set1_ps(1.f / 720.f), _mm_mul_ps(reduced, polynomial));
    polynomial = _mm_add_ps(_mm_set1_ps(1.f / 120.f), _mm_mul_ps(reduced, polynomial));
    polynomial = _mm_add_ps(_mm_set1_ps(1.f / 24.f), _mm_mul_ps(reduced, polynomial));
    polynomial = _mm_add_ps(_mm_set1_ps(1.f / 6.f), _mm_mul_ps(reduced, polynomial));
    polynomial = _mm_add_ps(_mm_set1_ps(0.5f), _mm_mul_ps(reduced, polynomial));
    polynomial = _mm_add_ps(_mm_set1_ps(1.f), _mm_mul_ps(reduced, polynomial));
    polynomial = _mm_add_ps(_mm_set1_ps(1.f), _mm_mul_ps(reduced, polynomial));

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
    const __m128 k2 = _mm_mul_ps(k, k);
    const __m128 k3 = _mm_mul_ps(k2, k);
    const __m128 k4 = _mm_mul_ps(k2, k2);
    const __m128 k5 = _mm_mul_ps(k3, k2);

    __m128 w = _mm_sub_ps(_mm_mul_ps(_mm_set1_ps(0.31938153f), k),
                          _mm_mul_ps(_mm_set1_ps(0.356563782f), k2));
    w = _mm_add_ps(w, _mm_mul_ps(_mm_set1_ps(1.781477937f), k3));
    w = _mm_add_ps(w, _mm_mul_ps(_mm_set1_ps(-1.821255978f), k4));
    w = _mm_add_ps(w, _mm_mul_ps(_mm_set1_ps(1.330274429f), k5));

    const __m128 expArgument = _mm_mul_ps(
        _mm_mul_ps(_mm_sub_ps(zero, L), L), _mm_set1_ps(.5f));
    const __m128 scale = _mm_mul_ps(
        _mm_set1_ps(0.39894228040f), black_scholes_exp_sse2(expArgument));
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
    const __m128 half = _mm_set1_ps(.5f);
    const __m128 absMask = _mm_castsi128_ps(_mm_set1_epi32(0x7fffffff));

    for (; count - i >= 4; i += 4) {
        const __m128 S = _mm_loadu_ps(Sa + i);
        const __m128 X = _mm_loadu_ps(Xa + i);
        const __m128 T = _mm_loadu_ps(Ta + i);
        const __m128 r = _mm_loadu_ps(ra + i);
        const __m128 v = _mm_loadu_ps(va + i);
        const __m128 ratio = _mm_div_ps(S, X);

        if (!black_scholes_sse2_positive_normal(ratio)) {
            black_scholes_serial(Sa + i, Xa + i, Ta + i, ra + i, va + i, result + i, 4);
            continue;
        }

        const __m128 logRatio = black_scholes_log_sse2(ratio);
        const __m128 rootT = _mm_sqrt_ps(T);
        const __m128 numerator = _mm_add_ps(
            logRatio,
            _mm_mul_ps(_mm_add_ps(r, _mm_mul_ps(_mm_mul_ps(v, v), half)), T));
        const __m128 vRootT = _mm_mul_ps(v, rootT);

        if (!black_scholes_sse2_finite(numerator) ||
            !black_scholes_sse2_nonzero_normal(vRootT)) {
            black_scholes_serial(Sa + i, Xa + i, Ta + i, ra + i, va + i, result + i, 4);
            continue;
        }

        const __m128 d1 = _mm_div_ps(numerator, vRootT);
        const __m128 d2 = _mm_sub_ps(d1, vRootT);
        if (!black_scholes_sse2_finite(d1) || !black_scholes_sse2_finite(d2)) {
            black_scholes_serial(Sa + i, Xa + i, Ta + i, ra + i, va + i, result + i, 4);
            continue;
        }

        const __m128 absD1 = _mm_and_ps(d1, absMask);
        const __m128 absD2 = _mm_and_ps(d2, absMask);
        const __m128 cndExp1 = _mm_mul_ps(
            _mm_mul_ps(_mm_sub_ps(zero, absD1), absD1), half);
        const __m128 cndExp2 = _mm_mul_ps(
            _mm_mul_ps(_mm_sub_ps(zero, absD2), absD2), half);
        const __m128 discountArgument = _mm_mul_ps(_mm_sub_ps(zero, r), T);
        if (!black_scholes_sse2_safe_exp_argument(cndExp1) ||
            !black_scholes_sse2_safe_exp_argument(cndExp2) ||
            !black_scholes_sse2_safe_exp_argument(discountArgument)) {
            black_scholes_serial(Sa + i, Xa + i, Ta + i, ra + i, va + i, result + i, 4);
            continue;
        }

        const __m128 cnd1 = black_scholes_cnd_sse2(d1);
        const __m128 cnd2 = black_scholes_cnd_sse2(d2);
        const __m128 discountedStrike = _mm_mul_ps(
            X, black_scholes_exp_sse2(discountArgument));
        const __m128 optionValue = _mm_sub_ps(
            _mm_mul_ps(S, cnd1), _mm_mul_ps(discountedStrike, cnd2));

        if (!black_scholes_sse2_finite(optionValue)) {
            black_scholes_serial(Sa + i, Xa + i, Ta + i, ra + i, va + i, result + i, 4);
            continue;
        }
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
