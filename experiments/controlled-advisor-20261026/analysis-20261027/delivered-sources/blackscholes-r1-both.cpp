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

#ifndef OPTIONS_DEFS_H
#define OPTIONS_DEFS_H 1

#define BINOMIAL_NUM 64

#endif // OPTIONS_DEFS_H

#include <algorithm>
#include <math.h>
#include <omp.h>

#if defined(__SSE2__)
#include <emmintrin.h>
#endif

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

#if defined(__SSE2__)
static inline __m128 log4_with_fallback(__m128 x) {
    const __m128 one = _mm_set1_ps(1.f);
    const __m128 minimum = _mm_set1_ps(0.0009765625f);
    const __m128 maximum = _mm_set1_ps(1024.f);
    const __m128 valid = _mm_and_ps(_mm_cmpge_ps(x, minimum), _mm_cmple_ps(x, maximum));
    const __m128 safe = _mm_or_ps(_mm_and_ps(valid, x), _mm_andnot_ps(valid, one));

    const __m128i bits = _mm_castps_si128(safe);
    const __m128i exponent = _mm_sub_epi32(
        _mm_and_si128(_mm_srli_epi32(bits, 23), _mm_set1_epi32(255)),
        _mm_set1_epi32(127));
    const __m128i mantissaBits = _mm_or_si128(
        _mm_and_si128(bits, _mm_set1_epi32(0x007fffff)),
        _mm_set1_epi32(0x3f800000));
    const __m128 mantissa = _mm_castsi128_ps(mantissaBits);
    const __m128 z = _mm_div_ps(_mm_sub_ps(mantissa, one), _mm_add_ps(mantissa, one));
    const __m128 z2 = _mm_mul_ps(z, z);

    __m128 series = _mm_set1_ps(1.f / 13.f);
    series = _mm_add_ps(_mm_mul_ps(series, z2), _mm_set1_ps(1.f / 11.f));
    series = _mm_add_ps(_mm_mul_ps(series, z2), _mm_set1_ps(1.f / 9.f));
    series = _mm_add_ps(_mm_mul_ps(series, z2), _mm_set1_ps(1.f / 7.f));
    series = _mm_add_ps(_mm_mul_ps(series, z2), _mm_set1_ps(1.f / 5.f));
    series = _mm_add_ps(_mm_mul_ps(series, z2), _mm_set1_ps(1.f / 3.f));
    series = _mm_add_ps(_mm_mul_ps(series, z2), one);
    const __m128 logMantissa = _mm_mul_ps(_mm_mul_ps(_mm_set1_ps(2.f), z), series);
    const __m128 logValue = _mm_add_ps(
        logMantissa,
        _mm_mul_ps(_mm_cvtepi32_ps(exponent), _mm_set1_ps(0.6931471805599453f)));

    float input[4];
    float output[4];
    _mm_storeu_ps(input, x);
    _mm_storeu_ps(output, logValue);
    for (int lane = 0; lane < 4; ++lane) {
        if (!(input[lane] >= 0.0009765625f && input[lane] <= 1024.f))
            output[lane] = logf(input[lane]);
    }
    return _mm_loadu_ps(output);
}

static inline __m128 exp4_with_fallback(__m128 x) {
    const __m128 zero = _mm_setzero_ps();
    const __m128 valid = _mm_and_ps(
        _mm_cmpge_ps(x, _mm_set1_ps(-80.f)),
        _mm_cmple_ps(x, zero));
    const __m128 safe = _mm_and_ps(valid, x);

    const __m128 y = _mm_mul_ps(safe, _mm_set1_ps(1.4426950408889634f));
    const __m128i exponent = _mm_cvttps_epi32(_mm_sub_ps(y, _mm_set1_ps(0.5f)));
    const __m128 exponentAsFloat = _mm_cvtepi32_ps(exponent);
    const __m128 reduced = _mm_sub_ps(
        safe,
        _mm_mul_ps(exponentAsFloat, _mm_set1_ps(0.6931471805599453f)));

    __m128 polynomial = _mm_set1_ps(1.f / 40320.f);
    polynomial = _mm_add_ps(_mm_mul_ps(polynomial, reduced), _mm_set1_ps(1.f / 5040.f));
    polynomial = _mm_add_ps(_mm_mul_ps(polynomial, reduced), _mm_set1_ps(1.f / 720.f));
    polynomial = _mm_add_ps(_mm_mul_ps(polynomial, reduced), _mm_set1_ps(1.f / 120.f));
    polynomial = _mm_add_ps(_mm_mul_ps(polynomial, reduced), _mm_set1_ps(1.f / 24.f));
    polynomial = _mm_add_ps(_mm_mul_ps(polynomial, reduced), _mm_set1_ps(1.f / 6.f));
    polynomial = _mm_add_ps(_mm_mul_ps(polynomial, reduced), _mm_set1_ps(0.5f));
    polynomial = _mm_add_ps(_mm_mul_ps(polynomial, reduced), _mm_set1_ps(1.f));
    polynomial = _mm_add_ps(_mm_mul_ps(polynomial, reduced), _mm_set1_ps(1.f));

    const __m128i scaleBits = _mm_slli_epi32(
        _mm_add_epi32(exponent, _mm_set1_epi32(127)), 23);
    const __m128 approximation = _mm_mul_ps(polynomial, _mm_castsi128_ps(scaleBits));

    // The common all-in-range case needs no scalar lane checks or stores.
    if (_mm_movemask_ps(valid) == 0xF)
        return approximation;

    float input[4];
    float output[4];
    _mm_storeu_ps(input, x);
    _mm_storeu_ps(output, approximation);
    for (int lane = 0; lane < 4; ++lane) {
        if (!(input[lane] >= -80.f && input[lane] <= 0.f))
            output[lane] = expf(input[lane]);
    }
    return _mm_loadu_ps(output);
}

// Separate discount helper: use T6's split-ln(2) reduction without changing
// T2's existing exponential approximation used by CND4.
static inline void exp4_discount_with_fallback(__m128 x, float output[4], int fallback_mask) {
    const __m128 zero = _mm_setzero_ps();
    const __m128 lower = _mm_set1_ps(-80.f);
    const __m128 clipped = _mm_min_ps(_mm_max_ps(x, lower), zero);

    const __m128 y = _mm_mul_ps(clipped, _mm_set1_ps(1.4426950408889634f));
    const __m128 n_as_float = _mm_sub_ps(y, _mm_set1_ps(0.5f));
    const __m128i n = _mm_cvttps_epi32(n_as_float);
    const __m128 nf = _mm_cvtepi32_ps(n);
    const __m128 ln2_hi = _mm_set1_ps(0.693359375f);
    const __m128 ln2_lo = _mm_set1_ps(-0.00021219444005469058f);
    __m128 reduced = _mm_sub_ps(clipped, _mm_mul_ps(nf, ln2_hi));
    reduced = _mm_sub_ps(reduced, _mm_mul_ps(nf, ln2_lo));

    __m128 polynomial = _mm_set1_ps(1.f / 40320.f);
    polynomial = _mm_add_ps(_mm_set1_ps(1.f / 5040.f), _mm_mul_ps(reduced, polynomial));
    polynomial = _mm_add_ps(_mm_set1_ps(1.f / 720.f), _mm_mul_ps(reduced, polynomial));
    polynomial = _mm_add_ps(_mm_set1_ps(1.f / 120.f), _mm_mul_ps(reduced, polynomial));
    polynomial = _mm_add_ps(_mm_set1_ps(1.f / 24.f), _mm_mul_ps(reduced, polynomial));
    polynomial = _mm_add_ps(_mm_set1_ps(1.f / 6.f), _mm_mul_ps(reduced, polynomial));
    polynomial = _mm_add_ps(_mm_set1_ps(0.5f), _mm_mul_ps(reduced, polynomial));
    polynomial = _mm_add_ps(_mm_set1_ps(1.f), _mm_mul_ps(reduced, polynomial));
    polynomial = _mm_add_ps(_mm_set1_ps(1.f), _mm_mul_ps(reduced, polynomial));

    const __m128i exponent_bits = _mm_slli_epi32(
        _mm_add_epi32(n, _mm_set1_epi32(127)), 23);
    _mm_storeu_ps(output, _mm_mul_ps(polynomial, _mm_castsi128_ps(exponent_bits)));

    float input[4];
    _mm_storeu_ps(input, x);
    for (int lane = 0; lane < 4; ++lane) {
        if (fallback_mask & (1 << lane))
            output[lane] = expf(input[lane]);
    }
}

static inline __m128 CND4(__m128 x) {
    const __m128 zero = _mm_setzero_ps();
    const __m128 one = _mm_set1_ps(1.f);
    const __m128 absolute = _mm_andnot_ps(_mm_set1_ps(-0.0f), x);
    const __m128 k = _mm_div_ps(
        one,
        _mm_add_ps(one, _mm_mul_ps(_mm_set1_ps(0.2316419f), absolute)));
    const __m128 k2 = _mm_mul_ps(k, k);
    const __m128 k3 = _mm_mul_ps(k2, k);
    const __m128 k4 = _mm_mul_ps(k2, k2);
    const __m128 k5 = _mm_mul_ps(k3, k2);

    __m128 w = _mm_sub_ps(_mm_mul_ps(_mm_set1_ps(0.31938153f), k),
                          _mm_mul_ps(_mm_set1_ps(0.356563782f), k2));
    w = _mm_add_ps(w, _mm_mul_ps(_mm_set1_ps(1.781477937f), k3));
    w = _mm_add_ps(w, _mm_mul_ps(_mm_set1_ps(-1.821255978f), k4));
    w = _mm_add_ps(w, _mm_mul_ps(_mm_set1_ps(1.330274429f), k5));
    const __m128 exponent = _mm_mul_ps(_mm_mul_ps(absolute, absolute), _mm_set1_ps(-0.5f));
    w = _mm_mul_ps(w, _mm_mul_ps(_mm_set1_ps(0.39894228040f), exp4_with_fallback(exponent)));

    const __m128 positive = _mm_cmpgt_ps(x, zero);
    return _mm_or_ps(_mm_and_ps(positive, _mm_sub_ps(one, w)), _mm_andnot_ps(positive, w));
}
#endif

static inline float black_scholes_one(float S, float X, float T, float r, float v) {
    float sqrtT = sqrtf(T);
    float vsqrtT = v * sqrtT;
    float d1 = (logf(S / X) + (r + v * v * .5f) * T) / vsqrtT;
    float d2 = d1 - vsqrtT;
    return S * CND(d1) - X * expf(-r * T) * CND(d2);
}

void black_scholes_serial(float Sa[], float Xa[], float Ta[], float ra[], float va[], float result[], int count) {
    int i = 0;
#if defined(__SSE2__)
    for (; i + 4 <= count; i += 4) {
        const __m128 S = _mm_loadu_ps(Sa + i);
        const __m128 X = _mm_loadu_ps(Xa + i);
        const __m128 T = _mm_loadu_ps(Ta + i);
        const __m128 r = _mm_loadu_ps(ra + i);
        const __m128 v = _mm_loadu_ps(va + i);

        const __m128 sqrtT = _mm_sqrt_ps(T);
        const __m128 vsqrtT = _mm_mul_ps(v, sqrtT);
        const __m128 logRatio = log4_with_fallback(_mm_div_ps(S, X));
        const __m128 vSquaredHalf = _mm_mul_ps(_mm_mul_ps(v, v), _mm_set1_ps(0.5f));
        const __m128 drift = _mm_mul_ps(_mm_add_ps(r, vSquaredHalf), T);
        const __m128 d1 = _mm_div_ps(_mm_add_ps(logRatio, drift), vsqrtT);
        const __m128 d2 = _mm_sub_ps(d1, vsqrtT);

        const __m128 discountExponent = _mm_mul_ps(_mm_sub_ps(_mm_setzero_ps(), r), T);
        const __m128 discountValid = _mm_and_ps(
            _mm_cmpge_ps(discountExponent, _mm_set1_ps(-80.f)),
            _mm_cmple_ps(discountExponent, _mm_setzero_ps()));
        const int discountFallbackMask = (~_mm_movemask_ps(discountValid)) & 0x0f;
        float discount[4];
        exp4_discount_with_fallback(discountExponent, discount, discountFallbackMask);

        const __m128 price = _mm_sub_ps(
            _mm_mul_ps(S, CND4(d1)),
            _mm_mul_ps(_mm_mul_ps(X, _mm_loadu_ps(discount)), CND4(d2)));
        _mm_storeu_ps(result + i, price);
    }
#endif
    for (; i < count; ++i)
        result[i] = black_scholes_one(Sa[i], Xa[i], Ta[i], ra[i], va[i]);
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

    if (threads <= 1) {
        black_scholes_serial(a, a + n, a + 2 * n, a + 3 * n, a + 4 * n, result, n);
        return;
    }

    const int useful_workers = n / 128;
    const int worker_count = std::min(threads, useful_workers);
    if (worker_count <= 1) {
        black_scholes_serial(a, a + n, a + 2 * n, a + 3 * n, a + 4 * n, result, n);
        return;
    }

    float* Sa = a;
    float* Xa = a + n;
    float* Ta = a + 2 * n;
    float* ra = a + 3 * n;
    float* va = a + 4 * n;
    const int chunk_count = (n - 1) / 128 + 1;

    // Each static iteration owns one contiguous 128-element chunk, except the tail.
    #pragma omp parallel for schedule(static) num_threads(worker_count)
    for (int chunk = 0; chunk < chunk_count; ++chunk) {
        const int begin = chunk * 128;
        const int count = std::min(128, n - begin);
        black_scholes_serial(Sa + begin, Xa + begin, Ta + begin, ra + begin, va + begin,
                             result + begin, count);
    }
}
