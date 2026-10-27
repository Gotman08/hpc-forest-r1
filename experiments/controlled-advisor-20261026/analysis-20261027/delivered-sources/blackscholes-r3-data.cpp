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

#if defined(__AVX__)
#include <immintrin.h>
#endif

// Cumulative normal distribution function.
static inline float CND(float X) {
    float L = fabsf(X);
    float k = 1.f / (1.f + 0.2316419f * L);
    float k2 = k * k;
    float k3 = k2 * k;
    float k4 = k2 * k2;
    float k5 = k3 * k2;

    const float invSqrt2Pi = 0.39894228040f;
    float w = (0.31938153f * k - 0.356563782f * k2 + 1.781477937f * k3 +
               -1.821255978f * k4 + 1.330274429f * k5);
    w *= invSqrt2Pi * expf(-L * L * .5f);

    if (X > 0.f)
        w = 1.f - w;
    return w;
}

#if defined(__AVX__)
// Approximate exp with AVX arithmetic on a safe interval. Exceptional and
// out-of-interval lanes retain the scalar libm behavior.
static inline __m256 exp_lanes_avx8(__m256 x) {
    const __m256 zero = _mm256_setzero_ps();
    const __m256 one = _mm256_set1_ps(1.f);
    const __m256 in_range = _mm256_and_ps(
        _mm256_cmp_ps(x, _mm256_set1_ps(-80.f), _CMP_GE_OQ),
        _mm256_cmp_ps(x, _mm256_set1_ps(80.f), _CMP_LE_OQ));
    const __m256 safe_x = _mm256_blendv_ps(zero, x, in_range);

    // Reduce x = k*ln(2) + r, with r near [-ln(2)/2, ln(2)/2].
    const __m256 k = _mm256_floor_ps(_mm256_add_ps(
        _mm256_mul_ps(safe_x, _mm256_set1_ps(1.4426950408889634f)),
        _mm256_set1_ps(0.5f)));
    const __m256 reduced_hi = _mm256_sub_ps(
        safe_x, _mm256_mul_ps(k, _mm256_set1_ps(0.693145751953125f)));
    const __m256 r = _mm256_sub_ps(
        reduced_hi, _mm256_mul_ps(k, _mm256_set1_ps(1.428606765330187e-6f)));

    // Degree-seven Taylor polynomial on the reduced interval.
    __m256 polynomial = _mm256_set1_ps(1.f / 5040.f);
    polynomial = _mm256_add_ps(_mm256_set1_ps(1.f / 720.f),
                               _mm256_mul_ps(r, polynomial));
    polynomial = _mm256_add_ps(_mm256_set1_ps(1.f / 120.f),
                               _mm256_mul_ps(r, polynomial));
    polynomial = _mm256_add_ps(_mm256_set1_ps(1.f / 24.f),
                               _mm256_mul_ps(r, polynomial));
    polynomial = _mm256_add_ps(_mm256_set1_ps(1.f / 6.f),
                               _mm256_mul_ps(r, polynomial));
    polynomial = _mm256_add_ps(_mm256_set1_ps(0.5f),
                               _mm256_mul_ps(r, polynomial));
    polynomial = _mm256_add_ps(one, _mm256_mul_ps(r, polynomial));
    polynomial = _mm256_add_ps(one, _mm256_mul_ps(r, polynomial));

    const __m256i exponent = _mm256_add_epi32(
        _mm256_cvttps_epi32(k), _mm256_set1_epi32(127));
    const __m256 scale = _mm256_castsi256_ps(
        _mm256_slli_epi32(exponent, 23));
    const __m256 approximate = _mm256_mul_ps(scale, polynomial);

    const int valid_lanes = _mm256_movemask_ps(in_range);
    if (valid_lanes == 0xff)
        return approximate;

    float input[8];
    float output[8];
    _mm256_storeu_ps(input, x);
    _mm256_storeu_ps(output, approximate);
    for (int lane = 0; lane < 8; ++lane) {
        if ((valid_lanes & (1 << lane)) == 0)
            output[lane] = expf(input[lane]);
    }
    return _mm256_loadu_ps(output);
}

// Approximate log(ratio) on [0.5, 2] with an atanh series; retain logf
// for lanes outside the approximation interval.
static inline __m256 log_ratio_avx8(__m256 ratio) {
    const __m256 one = _mm256_set1_ps(1.f);
    const __m256 in_range = _mm256_and_ps(
        _mm256_cmp_ps(ratio, _mm256_set1_ps(0.5f), _CMP_GE_OQ),
        _mm256_cmp_ps(ratio, _mm256_set1_ps(2.f), _CMP_LE_OQ));
    const __m256 safe_ratio = _mm256_blendv_ps(one, ratio, in_range);

    const __m256 z = _mm256_div_ps(
        _mm256_sub_ps(safe_ratio, one), _mm256_add_ps(safe_ratio, one));
    const __m256 z2 = _mm256_mul_ps(z, z);
    __m256 polynomial = _mm256_set1_ps(1.f / 13.f);
    polynomial = _mm256_add_ps(_mm256_set1_ps(1.f / 11.f),
                               _mm256_mul_ps(z2, polynomial));
    polynomial = _mm256_add_ps(_mm256_set1_ps(1.f / 9.f),
                               _mm256_mul_ps(z2, polynomial));
    polynomial = _mm256_add_ps(_mm256_set1_ps(1.f / 7.f),
                               _mm256_mul_ps(z2, polynomial));
    polynomial = _mm256_add_ps(_mm256_set1_ps(1.f / 5.f),
                               _mm256_mul_ps(z2, polynomial));
    polynomial = _mm256_add_ps(_mm256_set1_ps(1.f / 3.f),
                               _mm256_mul_ps(z2, polynomial));
    polynomial = _mm256_add_ps(one, _mm256_mul_ps(z2, polynomial));
    const __m256 approximation = _mm256_mul_ps(
        _mm256_mul_ps(_mm256_set1_ps(2.f), z), polynomial);

    const int valid_lanes = _mm256_movemask_ps(in_range);
    if (valid_lanes == 0xff)
        return approximation;

    float ratio_lane[8];
    float result_lane[8];
    _mm256_storeu_ps(ratio_lane, ratio);
    _mm256_storeu_ps(result_lane, approximation);
    for (int lane = 0; lane < 8; ++lane) {
        if ((valid_lanes & (1 << lane)) == 0)
            result_lane[lane] = logf(ratio_lane[lane]);
    }
    return _mm256_loadu_ps(result_lane);
}

static inline __m256 cnd_horner_avx8(__m256 x) {
    const __m256 zero = _mm256_setzero_ps();
    const __m256 one = _mm256_set1_ps(1.f);
    const __m256 sign_mask = _mm256_set1_ps(-0.0f);
    const __m256 abs_x = _mm256_andnot_ps(sign_mask, x);
    const __m256 k = _mm256_div_ps(
        one, _mm256_add_ps(one, _mm256_mul_ps(_mm256_set1_ps(0.2316419f), abs_x)));

    __m256 polynomial = _mm256_set1_ps(1.330274429f);
    polynomial = _mm256_add_ps(_mm256_set1_ps(-1.821255978f),
                               _mm256_mul_ps(k, polynomial));
    polynomial = _mm256_add_ps(_mm256_set1_ps(1.781477937f),
                               _mm256_mul_ps(k, polynomial));
    polynomial = _mm256_add_ps(_mm256_set1_ps(-0.356563782f),
                               _mm256_mul_ps(k, polynomial));
    polynomial = _mm256_add_ps(_mm256_set1_ps(0.31938153f),
                               _mm256_mul_ps(k, polynomial));
    polynomial = _mm256_mul_ps(k, polynomial);

    const __m256 exp_arg = _mm256_mul_ps(
        _mm256_mul_ps(abs_x, abs_x), _mm256_set1_ps(-0.5f));
    const __m256 scale = _mm256_mul_ps(
        _mm256_set1_ps(0.39894228040f), exp_lanes_avx8(exp_arg));
    const __m256 tail = _mm256_mul_ps(polynomial, scale);
    const __m256 positive_tail = _mm256_sub_ps(one, tail);
    const __m256 positive = _mm256_cmp_ps(x, zero, _CMP_GT_OQ);
    return _mm256_blendv_ps(tail, positive_tail, positive);
}

// Process one eight-element block with unaligned-safe accesses.
static inline void black_scholes_avx8(const float *Sa, const float *Xa,
                                      const float *Ta, const float *ra,
                                      const float *va, float *result, int i) {
    const __m256 s = _mm256_loadu_ps(Sa + i);
    const __m256 x = _mm256_loadu_ps(Xa + i);
    const __m256 t = _mm256_loadu_ps(Ta + i);
    const __m256 r = _mm256_loadu_ps(ra + i);
    const __m256 v = _mm256_loadu_ps(va + i);

    const __m256 ratio = _mm256_div_ps(s, x);
    const __m256 log_ratio = log_ratio_avx8(ratio);

    const __m256 sqrt_t = _mm256_sqrt_ps(t);
    const __m256 v_sqrt_t = _mm256_mul_ps(v, sqrt_t);
    const __m256 half_v_squared = _mm256_mul_ps(
        _mm256_mul_ps(v, v), _mm256_set1_ps(.5f));
    const __m256 drift = _mm256_mul_ps(
        _mm256_add_ps(r, half_v_squared), t);
    const __m256 d1 = _mm256_div_ps(
        _mm256_add_ps(log_ratio, drift), v_sqrt_t);
    const __m256 d2 = _mm256_sub_ps(d1, v_sqrt_t);

    const __m256 discount_arg = _mm256_mul_ps(
        _mm256_mul_ps(r, t), _mm256_set1_ps(-1.f));
    const __m256 discount = exp_lanes_avx8(discount_arg);
    const __m256 call_value = _mm256_mul_ps(s, cnd_horner_avx8(d1));
    const __m256 put_value = _mm256_mul_ps(
        _mm256_mul_ps(x, discount), cnd_horner_avx8(d2));
    _mm256_storeu_ps(result + i, _mm256_sub_ps(call_value, put_value));
}
#endif

// Evaluate a contiguous range; its start and length need not be vector-aligned.
static inline void black_scholes_range(const float *Sa, const float *Xa,
                                       const float *Ta, const float *ra,
                                       const float *va, float *result,
                                       int begin, int end) {
    int i = begin;
#if defined(__AVX__)
    for (; end - i >= 16; i += 16) {
        black_scholes_avx8(Sa, Xa, Ta, ra, va, result, i);
        black_scholes_avx8(Sa, Xa, Ta, ra, va, result, i + 8);
    }
    for (; end - i >= 8; i += 8)
        black_scholes_avx8(Sa, Xa, Ta, ra, va, result, i);
#endif
    for (; i < end; ++i) {
        float S = Sa[i], X = Xa[i];
        float T = Ta[i], r = ra[i];
        float v = va[i];
        float d1 = (logf(S / X) + (r + v * v * .5f) * T) / (v * sqrtf(T));
        float d2 = d1 - v * sqrtf(T);
        result[i] = S * CND(d1) - X * expf(-r * T) * CND(d2);
    }
}

void black_scholes_serial(float Sa[], float Xa[], float Ta[], float ra[],
                          float va[], float result[], int count) {
    black_scholes_range(Sa, Xa, Ta, ra, va, result, 0, count);
}

void binomial_put_serial(float Sa[], float Xa[], float Ta[], float ra[],
                         float va[], float result[], int count) {
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

extern "C" void run(const void *input1, const void *input2, void *output,
                    int n, int parameter, int threads) {
    (void)input2;
    (void)parameter;
    if (n <= 0)
        return;

    const float *a = static_cast<const float *>(input1);
    float *result = static_cast<float *>(output);
    const float *Sa = a;
    const float *Xa = a + n;
    const float *Ta = a + 2 * n;
    const float *ra = a + 3 * n;
    const float *va = a + 4 * n;

    if (threads <= 1) {
        black_scholes_range(Sa, Xa, Ta, ra, va, result, 0, n);
        return;
    }

    // Partition by the actual team size so every index is covered exactly once,
    // even if the runtime forms a smaller team than requested.
    #pragma omp parallel num_threads(threads)
    {
        const int team_size = omp_get_num_threads();
        const int thread_id = omp_get_thread_num();
        const int base = n / team_size;
        const int remainder = n % team_size;
        const int begin = thread_id * base + (thread_id < remainder ? thread_id : remainder);
        const int end = begin + base + (thread_id < remainder ? 1 : 0);
        black_scholes_range(Sa, Xa, Ta, ra, va, result, begin, end);
    }
}
