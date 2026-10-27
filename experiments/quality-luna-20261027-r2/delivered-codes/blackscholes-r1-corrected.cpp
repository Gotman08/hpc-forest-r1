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
#include <float.h>
#include <math.h>
#ifdef _OPENMP
#include <omp.h>
#endif

#if defined(__AVX2__)
#include <immintrin.h>
#endif

// Cumulative normal distribution function, with the polynomial factored around k^2.
static inline float CND(float X) {
    float L = fabsf(X);
    float k = 1.f / (1.f + 0.2316419f * L);
    float k2 = k * k;

    const float invSqrt2Pi = 0.39894228040f;
    float p01 = 0.31938153f - 0.356563782f * k;
    float p234 = 1.781477937f - 1.821255978f * k + 1.330274429f * k2;
    float w = k * (p01 + k2 * p234);
    w *= invSqrt2Pi * expf(-L * L * .5f);

    if (X > 0.f)
        w = 1.f - w;
    return w;
}

static inline void black_scholes_element(const float Sa[], const float Xa[], const float Ta[],
                                         const float ra[], const float va[], float result[], int i) {
    float S = Sa[i], X = Xa[i];
    float T = Ta[i], r = ra[i];
    float v = va[i];

    float d1 = (logf(S / X) + (r + v * v * .5f) * T) / (v * sqrtf(T));
    float d2 = d1 - v * sqrtf(T);

    result[i] = S * CND(d1) - X * expf(-r * T) * CND(d2);
}

#if defined(__AVX2__)
// AVX2 lane-wise logarithm for positive normal inputs. Unusual inputs are
// evaluated by the scalar path after the vector block has been written.
static inline __m256 log_positive_normal_avx2(__m256 x) {
    const __m256i fraction_mask = _mm256_set1_epi32(0x007fffff);
    const __m256i exponent_mask = _mm256_set1_epi32(0x000000ff);
    const __m256i one_bits = _mm256_set1_epi32(0x3f800000);
    const __m256i bias = _mm256_set1_epi32(127);

    __m256i bits = _mm256_castps_si256(x);
    __m256i exponent = _mm256_sub_epi32(
        _mm256_and_si256(_mm256_srli_epi32(bits, 23), exponent_mask), bias);
    __m256i mantissa_bits = _mm256_or_si256(
        _mm256_and_si256(bits, fraction_mask), one_bits);
    __m256 mantissa = _mm256_castsi256_ps(mantissa_bits);

    // log(m) = 2*z*(1 + z^2/3 + z^4/5 + ...), z=(m-1)/(m+1).
    __m256 z = _mm256_div_ps(
        _mm256_sub_ps(mantissa, _mm256_set1_ps(1.0f)),
        _mm256_add_ps(mantissa, _mm256_set1_ps(1.0f)));
    __m256 z2 = _mm256_mul_ps(z, z);
    __m256 p = _mm256_set1_ps(1.0f / 13.0f);
    p = _mm256_add_ps(_mm256_set1_ps(1.0f / 11.0f), _mm256_mul_ps(z2, p));
    p = _mm256_add_ps(_mm256_set1_ps(1.0f / 9.0f), _mm256_mul_ps(z2, p));
    p = _mm256_add_ps(_mm256_set1_ps(1.0f / 7.0f), _mm256_mul_ps(z2, p));
    p = _mm256_add_ps(_mm256_set1_ps(1.0f / 5.0f), _mm256_mul_ps(z2, p));
    p = _mm256_add_ps(_mm256_set1_ps(1.0f / 3.0f), _mm256_mul_ps(z2, p));
    __m256 log_mantissa = _mm256_mul_ps(
        _mm256_set1_ps(2.0f),
        _mm256_mul_ps(z, _mm256_add_ps(_mm256_set1_ps(1.0f), _mm256_mul_ps(z2, p))));

    return _mm256_add_ps(
        log_mantissa,
        _mm256_mul_ps(_mm256_cvtepi32_ps(exponent), _mm256_set1_ps(0.6931471805599453f)));
}

// Approximate exp on [-80, 0] with reduction to a small interval. Callers
// clamp vector CND and discount exponents to this range and use scalar expf
// for values outside it.
static inline __m256 exp_nonpositive_avx2(__m256 x) {
    __m256 y = _mm256_mul_ps(x, _mm256_set1_ps(1.4426950408889634f));
    __m256 rounded_n = _mm256_round_ps(
        y, _MM_FROUND_TO_NEAREST_INT | _MM_FROUND_NO_EXC);
    __m256i n_i = _mm256_cvttps_epi32(rounded_n);
    __m256 n = _mm256_cvtepi32_ps(n_i);

    __m256 r = _mm256_sub_ps(x, _mm256_mul_ps(n, _mm256_set1_ps(0.693145751953125f)));
    r = _mm256_sub_ps(r, _mm256_mul_ps(n, _mm256_set1_ps(1.428606765330187e-6f)));

    __m256 p = _mm256_set1_ps(1.0f / 5040.0f);
    p = _mm256_add_ps(_mm256_set1_ps(1.0f / 720.0f), _mm256_mul_ps(r, p));
    p = _mm256_add_ps(_mm256_set1_ps(1.0f / 120.0f), _mm256_mul_ps(r, p));
    p = _mm256_add_ps(_mm256_set1_ps(1.0f / 24.0f), _mm256_mul_ps(r, p));
    p = _mm256_add_ps(_mm256_set1_ps(1.0f / 6.0f), _mm256_mul_ps(r, p));
    p = _mm256_add_ps(_mm256_set1_ps(0.5f), _mm256_mul_ps(r, p));
    p = _mm256_add_ps(_mm256_set1_ps(1.0f), _mm256_mul_ps(r, p));
    p = _mm256_add_ps(_mm256_set1_ps(1.0f), _mm256_mul_ps(r, p));

    __m256i scale_bits = _mm256_slli_epi32(
        _mm256_add_epi32(n_i, _mm256_set1_epi32(127)), 23);
    return _mm256_mul_ps(p, _mm256_castsi256_ps(scale_bits));
}

static inline __m256 CND_avx2(__m256 x) {
    const __m256 zero = _mm256_setzero_ps();
    const __m256 abs_mask = _mm256_castsi256_ps(_mm256_set1_epi32(0x7fffffff));
    __m256 L = _mm256_and_ps(x, abs_mask);
    __m256 k = _mm256_div_ps(
        _mm256_set1_ps(1.0f),
        _mm256_add_ps(_mm256_set1_ps(1.0f), _mm256_mul_ps(_mm256_set1_ps(0.2316419f), L)));
    __m256 k2 = _mm256_mul_ps(k, k);
    __m256 k3 = _mm256_mul_ps(k2, k);
    __m256 k4 = _mm256_mul_ps(k2, k2);
    __m256 k5 = _mm256_mul_ps(k3, k2);

    __m256 w = _mm256_sub_ps(
        _mm256_mul_ps(_mm256_set1_ps(0.31938153f), k),
        _mm256_mul_ps(_mm256_set1_ps(0.356563782f), k2));
    w = _mm256_add_ps(w, _mm256_mul_ps(_mm256_set1_ps(1.781477937f), k3));
    w = _mm256_add_ps(w, _mm256_mul_ps(_mm256_set1_ps(-1.821255978f), k4));
    w = _mm256_add_ps(w, _mm256_mul_ps(_mm256_set1_ps(1.330274429f), k5));

    __m256 exponent = _mm256_mul_ps(_mm256_mul_ps(L, L), _mm256_set1_ps(-0.5f));
    exponent = _mm256_min_ps(_mm256_max_ps(exponent, _mm256_set1_ps(-80.0f)), zero);
    __m256 density = exp_nonpositive_avx2(exponent);
    w = _mm256_mul_ps(w, _mm256_mul_ps(_mm256_set1_ps(0.39894228040f), density));

    __m256 positive = _mm256_cmp_ps(x, zero, _CMP_GT_OQ);
    return _mm256_blendv_ps(w, _mm256_sub_ps(_mm256_set1_ps(1.0f), w), positive);
}

static void black_scholes_avx2_range(const float Sa[], const float Xa[], const float Ta[],
                                     const float ra[], const float va[], float result[], int count) {
    const __m256 zero = _mm256_setzero_ps();
    const __m256 max_float = _mm256_set1_ps(FLT_MAX);
    const __m256 abs_mask = _mm256_castsi256_ps(_mm256_set1_epi32(0x7fffffff));
    int i = 0;

    for (; count - i >= 8; i += 8) {
        __m256 S = _mm256_loadu_ps(Sa + i);
        __m256 X = _mm256_loadu_ps(Xa + i);
        __m256 T = _mm256_loadu_ps(Ta + i);
        __m256 r = _mm256_loadu_ps(ra + i);
        __m256 v = _mm256_loadu_ps(va + i);

        __m256 ratio = _mm256_div_ps(S, X);
        __m256 rootT = _mm256_sqrt_ps(T);
        __m256 numerator = _mm256_add_ps(
            log_positive_normal_avx2(ratio),
            _mm256_mul_ps(_mm256_add_ps(r, _mm256_mul_ps(_mm256_mul_ps(v, v), _mm256_set1_ps(0.5f))), T));
        __m256 vRootT = _mm256_mul_ps(v, rootT);
        __m256 d1 = _mm256_div_ps(numerator, vRootT);
        __m256 d2 = _mm256_sub_ps(d1, vRootT);

        __m256 discount_arg = _mm256_mul_ps(_mm256_mul_ps(r, T), _mm256_set1_ps(-1.0f));
        __m256 valid = _mm256_cmp_ps(S, zero, _CMP_GT_OQ);
        valid = _mm256_and_ps(valid, _mm256_cmp_ps(X, zero, _CMP_GT_OQ));
        valid = _mm256_and_ps(valid, _mm256_cmp_ps(T, zero, _CMP_GT_OQ));
        valid = _mm256_and_ps(valid, _mm256_cmp_ps(v, zero, _CMP_GT_OQ));
        valid = _mm256_and_ps(valid, _mm256_cmp_ps(_mm256_and_ps(S, abs_mask), max_float, _CMP_LE_OQ));
        valid = _mm256_and_ps(valid, _mm256_cmp_ps(_mm256_and_ps(X, abs_mask), max_float, _CMP_LE_OQ));
        valid = _mm256_and_ps(valid, _mm256_cmp_ps(_mm256_and_ps(T, abs_mask), max_float, _CMP_LE_OQ));
        valid = _mm256_and_ps(valid, _mm256_cmp_ps(_mm256_and_ps(r, abs_mask), max_float, _CMP_LE_OQ));
        valid = _mm256_and_ps(valid, _mm256_cmp_ps(_mm256_and_ps(v, abs_mask), max_float, _CMP_LE_OQ));
        valid = _mm256_and_ps(valid, _mm256_cmp_ps(ratio, _mm256_set1_ps(FLT_MIN), _CMP_GE_OQ));
        valid = _mm256_and_ps(valid, _mm256_cmp_ps(ratio, max_float, _CMP_LE_OQ));
        valid = _mm256_and_ps(valid, _mm256_cmp_ps(_mm256_and_ps(discount_arg, abs_mask), max_float, _CMP_LE_OQ));
        valid = _mm256_and_ps(valid, _mm256_cmp_ps(_mm256_and_ps(d1, abs_mask), _mm256_set1_ps(12.0f), _CMP_LE_OQ));
        valid = _mm256_and_ps(valid, _mm256_cmp_ps(_mm256_and_ps(d2, abs_mask), _mm256_set1_ps(12.0f), _CMP_LE_OQ));

        __m256 clamped_discount_arg = _mm256_min_ps(
            _mm256_max_ps(discount_arg, _mm256_set1_ps(-80.0f)), zero);
        __m256 discount_vector = exp_nonpositive_avx2(clamped_discount_arg);
        alignas(32) float discount_args[8];
        alignas(32) float discounts[8];
        _mm256_store_ps(discount_args, discount_arg);
        _mm256_store_ps(discounts, discount_vector);
        for (int lane = 0; lane < 8; ++lane) {
            if (!(discount_args[lane] >= -80.0f && discount_args[lane] <= 0.0f))
                discounts[lane] = expf(discount_args[lane]);
        }

        __m256 discount = _mm256_load_ps(discounts);
        __m256 value = _mm256_sub_ps(
            _mm256_mul_ps(S, CND_avx2(d1)),
            _mm256_mul_ps(X, _mm256_mul_ps(discount, CND_avx2(d2))));
        _mm256_storeu_ps(result + i, value);

        int valid_lanes = _mm256_movemask_ps(valid);
        for (int lane = 0; lane < 8; ++lane) {
            if ((valid_lanes & (1 << lane)) == 0)
                black_scholes_element(Sa, Xa, Ta, ra, va, result, i + lane);
        }
    }
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

static void black_scholes_run(const float Sa[], const float Xa[], const float Ta[],
                              const float ra[], const float va[], float result[],
                              int count, int threads) {
    if (count <= 0)
        return;

    const int workers = threads > 0 ? threads : 1;
#if defined(__AVX2__)
    const int blocks = count / 8;
    if (workers <= 1 || count <= workers || blocks == 0) {
        if (blocks > 0)
            black_scholes_avx2_range(Sa, Xa, Ta, ra, va, result, blocks * 8);
    } else {
#ifdef _OPENMP
#pragma omp parallel num_threads(workers)
        {
            const int team_size = omp_get_num_threads();
            const int tid = omp_get_thread_num();
            const int quotient = blocks / team_size;
            const int remainder = blocks % team_size;
            const int first_block = tid * quotient + (tid < remainder ? tid : remainder);
            const int local_blocks = quotient + (tid < remainder ? 1 : 0);
            if (local_blocks > 0) {
                const int begin = first_block * 8;
                const int local_count = local_blocks * 8;
                black_scholes_avx2_range(Sa + begin, Xa + begin, Ta + begin,
                                         ra + begin, va + begin, result + begin, local_count);
            }
        }
#else
        if (blocks > 0)
            black_scholes_avx2_range(Sa, Xa, Ta, ra, va, result, blocks * 8);
#endif
    }

    for (int i = blocks * 8; i < count; ++i)
        black_scholes_element(Sa, Xa, Ta, ra, va, result, i);
#else
    if (workers <= 1 || count <= workers) {
        for (int i = 0; i < count; ++i)
            black_scholes_element(Sa, Xa, Ta, ra, va, result, i);
    } else {
#ifdef _OPENMP
#pragma omp parallel num_threads(workers)
        {
            const int team_size = omp_get_num_threads();
            const int tid = omp_get_thread_num();
            const int quotient = count / team_size;
            const int remainder = count % team_size;
            const int begin = tid * quotient + (tid < remainder ? tid : remainder);
            const int end = begin + quotient + (tid < remainder ? 1 : 0);
            for (int i = begin; i < end; ++i)
                black_scholes_element(Sa, Xa, Ta, ra, va, result, i);
        }
#else
        for (int i = 0; i < count; ++i)
            black_scholes_element(Sa, Xa, Ta, ra, va, result, i);
#endif
    }
#endif
}

extern "C" void run(const void* input1, const void* input2, void* output,
                    int n, int parameter, int threads) {
    (void)input2;
    (void)parameter;
    if (n <= 0)
        return;

    const float* a = static_cast<const float*>(input1);
    float* result = static_cast<float*>(output);
    black_scholes_run(a, a + n, a + 2 * n, a + 3 * n, a + 4 * n,
                      result, n, threads);
}
