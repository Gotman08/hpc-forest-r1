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
#include <cstdint>
#include <cstring>
#include <cmath>
#include <omp.h>

#if defined(__AVX2__) || defined(_M_AVX2)
#include <immintrin.h>
#define BLACK_SCHOLES_HAS_AVX2 1
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

#if defined(BLACK_SCHOLES_HAS_AVX2)
static inline __m256 madd8(__m256 a, __m256 b, __m256 c) {
#if defined(__FMA__)
    return _mm256_fmadd_ps(a, b, c);
#else
    return _mm256_add_ps(_mm256_mul_ps(a, b), c);
#endif
}

// Range-reduced degree-7 exp approximation for the normal CDF and discount.
// Lanes outside the safe range use the scalar library implementation.
static inline __m256 exp8_approx_or_libm(__m256 x) {
    const __m256 lo = _mm256_set1_ps(-80.0f);
    const __m256 hi = _mm256_set1_ps(80.0f);
    const __m256 valid = _mm256_and_ps(
        _mm256_cmp_ps(x, lo, _CMP_GE_OQ),
        _mm256_cmp_ps(x, hi, _CMP_LE_OQ));
    const int valid_bits = _mm256_movemask_ps(valid);
    const __m256 safe_x = _mm256_blendv_ps(_mm256_setzero_ps(), x, valid);

    const __m256 log2e = _mm256_set1_ps(1.44269504088896341f);
    const __m256 scaled = _mm256_mul_ps(safe_x, log2e);
    const __m256 rounded = _mm256_round_ps(
        scaled, _MM_FROUND_TO_NEAREST_INT | _MM_FROUND_NO_EXC);
    const __m256i exponent = _mm256_cvttps_epi32(rounded);
    const __m256 exponent_f = _mm256_cvtepi32_ps(exponent);

    // Split ln(2) range reduction keeps the residual small.
    __m256 r = madd8(exponent_f, _mm256_set1_ps(-0.693359375f), safe_x);
    r = madd8(exponent_f, _mm256_set1_ps(0.00021219444005469058f), r);

    __m256 p = _mm256_set1_ps(1.0f / 5040.0f);
    p = madd8(p, r, _mm256_set1_ps(1.0f / 720.0f));
    p = madd8(p, r, _mm256_set1_ps(1.0f / 120.0f));
    p = madd8(p, r, _mm256_set1_ps(1.0f / 24.0f));
    p = madd8(p, r, _mm256_set1_ps(1.0f / 6.0f));
    p = madd8(p, r, _mm256_set1_ps(0.5f));
    p = madd8(p, r, _mm256_set1_ps(1.0f));
    p = madd8(p, r, _mm256_set1_ps(1.0f));

    const __m256i scale_bits = _mm256_slli_epi32(
        _mm256_add_epi32(exponent, _mm256_set1_epi32(127)), 23);
    __m256 result = _mm256_mul_ps(p, _mm256_castsi256_ps(scale_bits));

    if (valid_bits != 0xff) {
        alignas(32) float input_lanes[8];
        alignas(32) float result_lanes[8];
        _mm256_store_ps(input_lanes, x);
        _mm256_store_ps(result_lanes, result);
        for (int lane = 0; lane < 8; ++lane) {
            if ((valid_bits & (1 << lane)) == 0)
                result_lanes[lane] = expf(input_lanes[lane]);
        }
        result = _mm256_load_ps(result_lanes);
    }
    return result;
}

// Approximate log on a moderate positive range; use libm for other lanes.
// The odd atanh series is evaluated on the mantissa in [1, 2).
static inline __m256 log8_approx_or_libm(__m256 x) {
    const __m256 lo = _mm256_set1_ps(1.0e-30f);
    const __m256 hi = _mm256_set1_ps(1.0e30f);
    const __m256 valid = _mm256_and_ps(
        _mm256_cmp_ps(x, lo, _CMP_GE_OQ),
        _mm256_cmp_ps(x, hi, _CMP_LE_OQ));
    const int valid_bits = _mm256_movemask_ps(valid);
    const __m256 safe_x = _mm256_blendv_ps(_mm256_set1_ps(1.0f), x, valid);

    const __m256i bits = _mm256_castps_si256(safe_x);
    const __m256i exponent = _mm256_sub_epi32(
        _mm256_srli_epi32(bits, 23), _mm256_set1_epi32(127));
    const __m256i mantissa_bits = _mm256_or_si256(
        _mm256_and_si256(bits, _mm256_set1_epi32(0x007fffff)),
        _mm256_set1_epi32(0x3f800000));
    const __m256 mantissa = _mm256_castsi256_ps(mantissa_bits);

    const __m256 one = _mm256_set1_ps(1.0f);
    const __m256 y = _mm256_div_ps(
        _mm256_sub_ps(mantissa, one), _mm256_add_ps(mantissa, one));
    const __m256 y2 = _mm256_mul_ps(y, y);
    __m256 p = _mm256_set1_ps(1.0f / 13.0f);
    p = madd8(y2, p, _mm256_set1_ps(1.0f / 11.0f));
    p = madd8(y2, p, _mm256_set1_ps(1.0f / 9.0f));
    p = madd8(y2, p, _mm256_set1_ps(1.0f / 7.0f));
    p = madd8(y2, p, _mm256_set1_ps(1.0f / 5.0f));
    p = madd8(y2, p, _mm256_set1_ps(1.0f / 3.0f));
    p = madd8(y2, p, one);
    const __m256 log_mantissa = _mm256_mul_ps(
        _mm256_mul_ps(_mm256_set1_ps(2.0f), y), p);

    const __m256 exponent_f = _mm256_cvtepi32_ps(exponent);
    __m256 result = madd8(
        exponent_f, _mm256_set1_ps(0.693145751953125f), log_mantissa);
    result = madd8(
        exponent_f, _mm256_set1_ps(1.428606765330187e-6f), result);

    if (valid_bits != 0xff) {
        alignas(32) float input_lanes[8];
        alignas(32) float result_lanes[8];
        _mm256_store_ps(input_lanes, x);
        _mm256_store_ps(result_lanes, result);
        for (int lane = 0; lane < 8; ++lane) {
            if ((valid_bits & (1 << lane)) == 0)
                result_lanes[lane] = logf(input_lanes[lane]);
        }
        result = _mm256_load_ps(result_lanes);
    }
    return result;
}

// Evaluate the original CND polynomial in Horner form across eight lanes.
static inline __m256 cnd8(__m256 x) {
    const __m256 abs_mask = _mm256_castsi256_ps(_mm256_set1_epi32(0x7fffffff));
    const __m256 L = _mm256_and_ps(x, abs_mask);
    const __m256 one = _mm256_set1_ps(1.0f);
    const __m256 k = _mm256_div_ps(
        one, _mm256_add_ps(one, _mm256_mul_ps(_mm256_set1_ps(0.2316419f), L)));

    __m256 w = _mm256_set1_ps(1.330274429f);
    w = _mm256_add_ps(_mm256_mul_ps(w, k), _mm256_set1_ps(-1.821255978f));
    w = _mm256_add_ps(_mm256_mul_ps(w, k), _mm256_set1_ps(1.781477937f));
    w = _mm256_add_ps(_mm256_mul_ps(w, k), _mm256_set1_ps(-0.356563782f));
    w = _mm256_add_ps(_mm256_mul_ps(w, k), _mm256_set1_ps(0.31938153f));
    w = _mm256_mul_ps(k, w);
    w = _mm256_mul_ps(w, _mm256_set1_ps(0.39894228040f));

    const __m256 exponent = _mm256_mul_ps(
        _mm256_mul_ps(_mm256_set1_ps(-0.5f), L), L);
    w = _mm256_mul_ps(w, exp8_approx_or_libm(exponent));

    const __m256 positive = _mm256_cmp_ps(x, _mm256_setzero_ps(), _CMP_GT_OQ);
    return _mm256_blendv_ps(w, _mm256_sub_ps(one, w), positive);
}

// Compute one eight-option vector group.
static inline void black_scholes_avx8(const float* Sa, const float* Xa,
                                      const float* Ta, const float* ra,
                                      const float* va, float* result) {
    const __m256 S = _mm256_loadu_ps(Sa);
    const __m256 X = _mm256_loadu_ps(Xa);
    const __m256 T = _mm256_loadu_ps(Ta);
    const __m256 r = _mm256_loadu_ps(ra);
    const __m256 v = _mm256_loadu_ps(va);

    const __m256 sqrt_t_v = _mm256_sqrt_ps(T);
    const __m256 log_ratio_v = log8_approx_or_libm(_mm256_div_ps(S, X));
    const __m256 v_sqrt_t = _mm256_mul_ps(v, sqrt_t_v);
    const __m256 half_v2 = _mm256_mul_ps(
        _mm256_mul_ps(v, v), _mm256_set1_ps(0.5f));
    const __m256 drift = _mm256_add_ps(r, half_v2);
    const __m256 numerator = _mm256_add_ps(
        log_ratio_v, _mm256_mul_ps(drift, T));
    const __m256 d1 = _mm256_div_ps(numerator, v_sqrt_t);
    const __m256 d2 = _mm256_sub_ps(d1, v_sqrt_t);

    const __m256 discount_exponent = _mm256_sub_ps(
        _mm256_setzero_ps(), _mm256_mul_ps(r, T));
    const __m256 discount = exp8_approx_or_libm(discount_exponent);
    const __m256 cnd1 = cnd8(d1);
    const __m256 cnd2 = cnd8(d2);
    const __m256 price = _mm256_sub_ps(
        _mm256_mul_ps(S, cnd1),
        _mm256_mul_ps(_mm256_mul_ps(X, discount), cnd2));
    _mm256_storeu_ps(result, price);
}

// Evaluate two independent AVX2 groups together to expose instruction-level
// parallelism while keeping the same per-group approximations and fallbacks.
static inline void black_scholes_avx16(const float* Sa, const float* Xa,
                                       const float* Ta, const float* ra,
                                       const float* va, float* result) {
    const __m256 S0 = _mm256_loadu_ps(Sa);
    const __m256 X0 = _mm256_loadu_ps(Xa);
    const __m256 T0 = _mm256_loadu_ps(Ta);
    const __m256 r0 = _mm256_loadu_ps(ra);
    const __m256 v0 = _mm256_loadu_ps(va);
    const __m256 S1 = _mm256_loadu_ps(Sa + 8);
    const __m256 X1 = _mm256_loadu_ps(Xa + 8);
    const __m256 T1 = _mm256_loadu_ps(Ta + 8);
    const __m256 r1 = _mm256_loadu_ps(ra + 8);
    const __m256 v1 = _mm256_loadu_ps(va + 8);

    const __m256 sqrt_t0 = _mm256_sqrt_ps(T0);
    const __m256 sqrt_t1 = _mm256_sqrt_ps(T1);
    const __m256 log_ratio0 = log8_approx_or_libm(_mm256_div_ps(S0, X0));
    const __m256 log_ratio1 = log8_approx_or_libm(_mm256_div_ps(S1, X1));

    const __m256 v_sqrt_t0 = _mm256_mul_ps(v0, sqrt_t0);
    const __m256 v_sqrt_t1 = _mm256_mul_ps(v1, sqrt_t1);
    const __m256 half_v2_0 = _mm256_mul_ps(
        _mm256_mul_ps(v0, v0), _mm256_set1_ps(0.5f));
    const __m256 half_v2_1 = _mm256_mul_ps(
        _mm256_mul_ps(v1, v1), _mm256_set1_ps(0.5f));
    const __m256 drift0 = _mm256_add_ps(r0, half_v2_0);
    const __m256 drift1 = _mm256_add_ps(r1, half_v2_1);
    const __m256 numerator0 = _mm256_add_ps(
        log_ratio0, _mm256_mul_ps(drift0, T0));
    const __m256 numerator1 = _mm256_add_ps(
        log_ratio1, _mm256_mul_ps(drift1, T1));
    const __m256 d10 = _mm256_div_ps(numerator0, v_sqrt_t0);
    const __m256 d11 = _mm256_div_ps(numerator1, v_sqrt_t1);
    const __m256 d20 = _mm256_sub_ps(d10, v_sqrt_t0);
    const __m256 d21 = _mm256_sub_ps(d11, v_sqrt_t1);

    const __m256 discount_exponent0 = _mm256_sub_ps(
        _mm256_setzero_ps(), _mm256_mul_ps(r0, T0));
    const __m256 discount_exponent1 = _mm256_sub_ps(
        _mm256_setzero_ps(), _mm256_mul_ps(r1, T1));
    const __m256 discount0 = exp8_approx_or_libm(discount_exponent0);
    const __m256 discount1 = exp8_approx_or_libm(discount_exponent1);

    const __m256 cnd10 = cnd8(d10);
    const __m256 cnd11 = cnd8(d11);
    const __m256 cnd20 = cnd8(d20);
    const __m256 cnd21 = cnd8(d21);

    const __m256 price0 = _mm256_sub_ps(
        _mm256_mul_ps(S0, cnd10),
        _mm256_mul_ps(_mm256_mul_ps(X0, discount0), cnd20));
    const __m256 price1 = _mm256_sub_ps(
        _mm256_mul_ps(S1, cnd11),
        _mm256_mul_ps(_mm256_mul_ps(X1, discount1), cnd21));
    _mm256_storeu_ps(result, price0);
    _mm256_storeu_ps(result + 8, price1);
}

static void black_scholes_avx2(float Sa[], float Xa[], float Ta[], float ra[], float va[], float result[], int count) {
    int i = 0;
    for (; count - i >= 16; i += 16)
        black_scholes_avx16(Sa + i, Xa + i, Ta + i, ra + i, va + i, result + i);

    if (count - i >= 8) {
        black_scholes_avx8(Sa + i, Xa + i, Ta + i, ra + i, va + i, result + i);
        i += 8;
    }

    // Preserve the scalar implementation for arbitrary counts and tails.
    if (i < count)
        black_scholes_serial(Sa + i, Xa + i, Ta + i, ra + i, va + i,
                             result + i, count - i);
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
#if defined(BLACK_SCHOLES_HAS_AVX2)
        black_scholes_avx2(S, X, T, r, v, result, n);
#else
        black_scholes_serial(S, X, T, r, v, result, n);
#endif
        return;
    }

#if defined(BLACK_SCHOLES_HAS_AVX2)
    // Partition complete SIMD groups; process the single remainder after the barrier.
    const int vector_count = n / 8;
    #pragma omp parallel for schedule(static) num_threads(threads)
    for (int part = 0; part < threads; ++part) {
        const int first_vector = (int)(((long long)vector_count * part) / threads);
        const int last_vector = (int)(((long long)vector_count * (part + 1)) / threads);
        const int first = first_vector * 8;
        const int count = (last_vector - first_vector) * 8;
        black_scholes_avx2(S + first, X + first, T + first, r + first, v + first,
                           result + first, count);
    }
    const int tail = vector_count * 8;
    if (tail < n)
        black_scholes_serial(S + tail, X + tail, T + tail, r + tail, v + tail,
                             result + tail, n - tail);
#else
    #pragma omp parallel for schedule(static) num_threads(threads)
    for (int part = 0; part < threads; ++part) {
        const int first = (int)(((long long)n * part) / threads);
        const int last = (int)(((long long)n * (part + 1)) / threads);
        black_scholes_serial(S + first, X + first, T + first, r + first, v + first,
                             result + first, last - first);
    }
#endif
}
