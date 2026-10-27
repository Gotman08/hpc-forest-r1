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
#include <cstddef>
#include <cstdint>
#include <cstring>
#include <cmath>
#include <omp.h>

#if defined(__AVX2__)
#include <immintrin.h>

// Approximate log(x) for positive normal lanes; use libm for all other lanes.
static inline __m256 log8_safe(__m256 x) {
    const __m256 minNormal = _mm256_set1_ps(1.1754943508222875e-38f);
    const __m256 maxFinite = _mm256_set1_ps(3.402823466e+38f);
    const __m256 valid = _mm256_and_ps(
        _mm256_cmp_ps(x, minNormal, _CMP_GE_OQ),
        _mm256_cmp_ps(x, maxFinite, _CMP_LE_OQ));

    const __m256i bits = _mm256_castps_si256(x);
    __m256i exponent = _mm256_sub_epi32(
        _mm256_and_si256(_mm256_srli_epi32(bits, 23), _mm256_set1_epi32(255)),
        _mm256_set1_epi32(127));
    const __m256i mantissaBits = _mm256_or_si256(
        _mm256_and_si256(bits, _mm256_set1_epi32(0x007fffff)),
        _mm256_set1_epi32(0x3f800000));
    __m256 mantissa = _mm256_castsi256_ps(mantissaBits);

    const __m256 aboveSqrt2 = _mm256_cmp_ps(
        mantissa, _mm256_set1_ps(1.4142135623730951f), _CMP_GT_OQ);
    mantissa = _mm256_blendv_ps(
        mantissa, _mm256_mul_ps(mantissa, _mm256_set1_ps(0.5f)), aboveSqrt2);
    exponent = _mm256_add_epi32(
        exponent,
        _mm256_and_si256(_mm256_castps_si256(aboveSqrt2), _mm256_set1_epi32(1)));

    const __m256 one = _mm256_set1_ps(1.0f);
    const __m256 y = _mm256_div_ps(
        _mm256_sub_ps(mantissa, one), _mm256_add_ps(mantissa, one));
    const __m256 y2 = _mm256_mul_ps(y, y);
    __m256 series = _mm256_set1_ps(1.0f / 9.0f);
    series = _mm256_add_ps(_mm256_set1_ps(1.0f / 7.0f), _mm256_mul_ps(y2, series));
    series = _mm256_add_ps(_mm256_set1_ps(1.0f / 5.0f), _mm256_mul_ps(y2, series));
    series = _mm256_add_ps(_mm256_set1_ps(1.0f / 3.0f), _mm256_mul_ps(y2, series));
    series = _mm256_add_ps(one, _mm256_mul_ps(y2, series));
    const __m256 logMantissa = _mm256_mul_ps(
        _mm256_mul_ps(_mm256_set1_ps(2.0f), y), series);

    const __m256 exponentF = _mm256_cvtepi32_ps(exponent);
    const __m256 logExponent = _mm256_add_ps(
        _mm256_mul_ps(exponentF, _mm256_set1_ps(0.693145751953125f)),
        _mm256_mul_ps(exponentF, _mm256_set1_ps(1.428606765330187e-6f)));
    __m256 result = _mm256_add_ps(logExponent, logMantissa);

    const int invalid = (~_mm256_movemask_ps(valid)) & 0xff;
    if (invalid != 0) {
        float inputLanes[8];
        float resultLanes[8];
        _mm256_storeu_ps(inputLanes, x);
        _mm256_storeu_ps(resultLanes, result);
        for (int lane = 0; lane < 8; ++lane) {
            if (invalid & (1 << lane))
                resultLanes[lane] = logf(inputLanes[lane]);
        }
        result = _mm256_loadu_ps(resultLanes);
    }
    return result;
}

// Approximate exp(x) for the common CND range [-80, 0]. Out-of-range lanes
// use libm so exceptional and extreme values retain the scalar behavior.
static inline __m256 exp8_approx_or_scalar(__m256 x) {
    const __m256 zero = _mm256_setzero_ps();
    const __m256 valid = _mm256_and_ps(
        _mm256_cmp_ps(x, _mm256_set1_ps(-80.0f), _CMP_GE_OQ),
        _mm256_cmp_ps(x, zero, _CMP_LE_OQ));

    const __m256 z = _mm256_mul_ps(x, _mm256_set1_ps(1.4426950408889634f));
    const __m256 n = _mm256_round_ps(
        z, _MM_FROUND_TO_NEAREST_INT | _MM_FROUND_NO_EXC);
    const __m256 r = _mm256_sub_ps(
        _mm256_sub_ps(x, _mm256_mul_ps(n, _mm256_set1_ps(0.693145751953125f))),
        _mm256_mul_ps(n, _mm256_set1_ps(1.428606765330187e-6f)));

    // Degree-seven Taylor polynomial on the range-reduced interval.
    __m256 p = _mm256_set1_ps(0.00019841270113832384f);
    p = _mm256_add_ps(_mm256_set1_ps(0.0013888889225199819f), _mm256_mul_ps(r, p));
    p = _mm256_add_ps(_mm256_set1_ps(0.008333333767950535f), _mm256_mul_ps(r, p));
    p = _mm256_add_ps(_mm256_set1_ps(0.0416666679084301f), _mm256_mul_ps(r, p));
    p = _mm256_add_ps(_mm256_set1_ps(0.1666666716337204f), _mm256_mul_ps(r, p));
    p = _mm256_add_ps(_mm256_set1_ps(0.5f), _mm256_mul_ps(r, p));
    p = _mm256_add_ps(_mm256_set1_ps(1.0f), _mm256_mul_ps(r, p));
    p = _mm256_add_ps(_mm256_set1_ps(1.0f), _mm256_mul_ps(r, p));

    const __m256i exponent = _mm256_add_epi32(
        _mm256_cvttps_epi32(n), _mm256_set1_epi32(127));
    const __m256 scale = _mm256_castsi256_ps(
        _mm256_slli_epi32(exponent, 23));
    const __m256 approximation = _mm256_mul_ps(p, scale);

    alignas(32) float arguments[8];
    alignas(32) float values[8];
    _mm256_storeu_ps(arguments, x);
    _mm256_storeu_ps(values, approximation);
    const int valid_lanes = _mm256_movemask_ps(valid);
    for (int lane = 0; lane < 8; ++lane) {
        if ((valid_lanes & (1 << lane)) == 0)
            values[lane] = expf(arguments[lane]);
    }
    return _mm256_loadu_ps(values);
}

// Range-reduced exponential for discount factors, with libm fallback outside
// the safe finite range. Unlike the CND exponential, this accepts positive x.
static inline __m256 exp8_general_or_scalar(__m256 x) {
    const __m256 zero = _mm256_setzero_ps();
    const __m256 absX = _mm256_and_ps(
        x, _mm256_castsi256_ps(_mm256_set1_epi32(0x7fffffff)));
    const __m256 valid = _mm256_cmp_ps(absX, _mm256_set1_ps(80.0f), _CMP_LT_OQ);
    const __m256 safeX = _mm256_blendv_ps(zero, x, valid);

    const __m256 z = _mm256_mul_ps(safeX, _mm256_set1_ps(1.4426950408889634f));
    const __m256 n = _mm256_round_ps(
        z, _MM_FROUND_TO_NEAREST_INT | _MM_FROUND_NO_EXC);
    const __m256 r = _mm256_sub_ps(
        _mm256_sub_ps(safeX, _mm256_mul_ps(n, _mm256_set1_ps(0.693145751953125f))),
        _mm256_mul_ps(n, _mm256_set1_ps(1.428606765330187e-6f)));

    __m256 p = _mm256_set1_ps(0.00019841270113832384f);
    p = _mm256_add_ps(_mm256_set1_ps(0.0013888889225199819f), _mm256_mul_ps(r, p));
    p = _mm256_add_ps(_mm256_set1_ps(0.008333333767950535f), _mm256_mul_ps(r, p));
    p = _mm256_add_ps(_mm256_set1_ps(0.0416666679084301f), _mm256_mul_ps(r, p));
    p = _mm256_add_ps(_mm256_set1_ps(0.1666666716337204f), _mm256_mul_ps(r, p));
    p = _mm256_add_ps(_mm256_set1_ps(0.5f), _mm256_mul_ps(r, p));
    p = _mm256_add_ps(_mm256_set1_ps(1.0f), _mm256_mul_ps(r, p));
    p = _mm256_add_ps(_mm256_set1_ps(1.0f), _mm256_mul_ps(r, p));

    const __m256i exponent = _mm256_add_epi32(
        _mm256_cvttps_epi32(n), _mm256_set1_epi32(127));
    const __m256 scale = _mm256_castsi256_ps(
        _mm256_slli_epi32(exponent, 23));
    const __m256 approximation = _mm256_mul_ps(p, scale);

    const int validLanes = _mm256_movemask_ps(valid);
    if (validLanes != 0xff) {
        alignas(32) float arguments[8];
        alignas(32) float values[8];
        _mm256_storeu_ps(arguments, x);
        _mm256_storeu_ps(values, approximation);
        for (int lane = 0; lane < 8; ++lane) {
            if ((validLanes & (1 << lane)) == 0)
                values[lane] = expf(arguments[lane]);
        }
        return _mm256_loadu_ps(values);
    }
    return approximation;
}

// Vector arithmetic and CND polynomial with a lane-wise exp approximation.
static inline __m256 CND8(__m256 X) {
    const __m256 zero = _mm256_setzero_ps();
    const __m256 one = _mm256_set1_ps(1.0f);
    const __m256 half = _mm256_set1_ps(0.5f);
    const __m256 invSqrt2Pi = _mm256_set1_ps(0.39894228040f);
    const __m256 L = _mm256_andnot_ps(_mm256_set1_ps(-0.0f), X);

    const __m256 denom = _mm256_add_ps(
        one, _mm256_mul_ps(_mm256_set1_ps(0.2316419f), L));
    const __m256 k = _mm256_div_ps(one, denom);
    const __m256 k2 = _mm256_mul_ps(k, k);
    const __m256 k3 = _mm256_mul_ps(k2, k);
    const __m256 k4 = _mm256_mul_ps(k2, k2);
    const __m256 k5 = _mm256_mul_ps(k3, k2);

    __m256 w = _mm256_sub_ps(
        _mm256_mul_ps(_mm256_set1_ps(0.31938153f), k),
        _mm256_mul_ps(_mm256_set1_ps(0.356563782f), k2));
    w = _mm256_add_ps(w, _mm256_mul_ps(_mm256_set1_ps(1.781477937f), k3));
    w = _mm256_add_ps(w, _mm256_mul_ps(_mm256_set1_ps(-1.821255978f), k4));
    w = _mm256_add_ps(w, _mm256_mul_ps(_mm256_set1_ps(1.330274429f), k5));

    const __m256 negL = _mm256_sub_ps(zero, L);
    const __m256 expArg = _mm256_mul_ps(_mm256_mul_ps(negL, L), half);
    const __m256 expValue = exp8_approx_or_scalar(expArg);

    w = _mm256_mul_ps(w, _mm256_mul_ps(invSqrt2Pi, expValue));
    const __m256 positive = _mm256_cmp_ps(X, zero, _CMP_GT_OQ);
    const __m256 upperTail = _mm256_sub_ps(one, w);
    return _mm256_blendv_ps(w, upperTail, positive);
}

static inline void black_scholes_avx2_block(
    float Sa[], float Xa[], float Ta[], float ra[], float va[], float result[], std::size_t i) {
    const __m256 zero = _mm256_setzero_ps();
    const __m256 half = _mm256_set1_ps(0.5f);

    const __m256 S = _mm256_loadu_ps(Sa + i);
    const __m256 X = _mm256_loadu_ps(Xa + i);
    const __m256 T = _mm256_loadu_ps(Ta + i);
    const __m256 r = _mm256_loadu_ps(ra + i);
    const __m256 v = _mm256_loadu_ps(va + i);

    const __m256 logValue = log8_safe(_mm256_div_ps(S, X));

    const __m256 sqrtT = _mm256_sqrt_ps(T);
    const __m256 vSqrtT = _mm256_mul_ps(v, sqrtT);
    const __m256 vvHalf = _mm256_mul_ps(_mm256_mul_ps(v, v), half);
    const __m256 drift = _mm256_mul_ps(_mm256_add_ps(r, vvHalf), T);
    const __m256 d1 = _mm256_div_ps(_mm256_add_ps(logValue, drift), vSqrtT);
    const __m256 d2 = _mm256_sub_ps(d1, vSqrtT);

    const __m256 discountArg = _mm256_mul_ps(_mm256_sub_ps(zero, r), T);
    const __m256 discount = exp8_general_or_scalar(discountArg);

    const __m256 callValue = _mm256_mul_ps(S, CND8(d1));
    const __m256 putValue = _mm256_mul_ps(
        _mm256_mul_ps(X, discount), CND8(d2));
    _mm256_storeu_ps(result + i, _mm256_sub_ps(callValue, putValue));
}
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
    if (count <= 0)
        return;

#if defined(__AVX2__)
    const std::size_t n = static_cast<std::size_t>(count);
    std::size_t i = 0;

    for (; i + 8 <= n; i += 8)
        black_scholes_avx2_block(Sa, Xa, Ta, ra, va, result, i);

    // Handle every remaining element without reading or writing past an array.
    for (; i < n; ++i) {
        float S = Sa[i], X = Xa[i];
        float T = Ta[i], r = ra[i];
        float v = va[i];

        float d1 = (logf(S / X) + (r + v * v * .5f) * T) / (v * sqrtf(T));
        float d2 = d1 - v * sqrtf(T);

        result[i] = S * CND(d1) - X * expf(-r * T) * CND(d2);
    }
#else
    // This remains a per-thread kernel: SIMD is requested, but no work is scheduled here.
    #pragma omp simd
    for (int i = 0; i < count; ++i) {
        float S = Sa[i], X = Xa[i];
        float T = Ta[i], r = ra[i];
        float v = va[i];

        float d1 = (logf(S / X) + (r + v * v * .5f) * T) / (v * sqrtf(T));
        float d2 = d1 - v * sqrtf(T);

        result[i] = S * CND(d1) - X * expf(-r * T) * CND(d2);
    }
#endif
}

void black_scholes_parallel(float Sa[], float Xa[], float Ta[], float ra[], float va[], float result[], int count, int threads) {
    if (count <= 0)
        return;
    if (threads <= 1) {
        black_scholes_serial(Sa, Xa, Ta, ra, va, result, count);
        return;
    }

#if defined(__AVX2__)
    // Each scheduled task owns one eight-element SIMD block or the final scalar tail.
    const int num_blocks = (count - 1) / 8 + 1;
    const int team_size = std::min(threads, num_blocks);
    #pragma omp parallel for schedule(static) num_threads(team_size)
    for (int block = 0; block < num_blocks; ++block) {
        const int start = block * 8;
        if (count - start >= 8) {
            black_scholes_avx2_block(
                Sa, Xa, Ta, ra, va, result, static_cast<std::size_t>(start));
        } else {
            for (int i = start; i < count; ++i) {
                float S = Sa[i], X = Xa[i];
                float T = Ta[i], r = ra[i];
                float v = va[i];

                float d1 = (logf(S / X) + (r + v * v * .5f) * T) / (v * sqrtf(T));
                float d2 = d1 - v * sqrtf(T);

                result[i] = S * CND(d1) - X * expf(-r * T) * CND(d2);
            }
        }
    }
#else
    const int team_size = std::min(threads, count);
    #pragma omp parallel for simd schedule(static) num_threads(team_size)
    for (int i = 0; i < count; ++i) {
        float S = Sa[i], X = Xa[i];
        float T = Ta[i], r = ra[i];
        float v = va[i];

        float d1 = (logf(S / X) + (r + v * v * .5f) * T) / (v * sqrtf(T));
        float d2 = d1 - v * sqrtf(T);

        result[i] = S * CND(d1) - X * expf(-r * T) * CND(d2);
    }
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

extern "C" void run(const void* input1, const void* input2, void* output, int n, int parameter, int threads) {
    if (n <= 0)
        return;

    float* a = (float*)input1;
    float* result = (float*)output;
    float* S = a;
    float* X = a + n;
    float* T = a + 2 * n;
    float* r = a + 3 * n;
    float* v = a + 4 * n;

    if (threads <= 1) {
        black_scholes_serial(S, X, T, r, v, result, n);
    } else {
        black_scholes_parallel(S, X, T, r, v, result, n, threads);
    }
}
