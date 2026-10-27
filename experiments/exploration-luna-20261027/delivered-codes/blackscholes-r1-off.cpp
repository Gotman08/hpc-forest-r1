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
#include <omp.h>

#if defined(__AVX2__)
#include <immintrin.h>
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

#if defined(__AVX2__)
static inline __m256 exp8_with_fallback(__m256 x) {
    const __m256 zero = _mm256_setzero_ps();
    const __m256 one = _mm256_set1_ps(1.0f);
    const __m256 half = _mm256_set1_ps(0.5f);
    const __m256 lower_bound = _mm256_set1_ps(-10.0f);
    const __m256 inv_ln2 = _mm256_set1_ps(1.4426950408889634f);
    const __m256 ln2_hi = _mm256_set1_ps(0.693145751953125f);
    const __m256 ln2_lo = _mm256_set1_ps(1.428606765330187045e-6f);

    const __m256 valid = _mm256_and_ps(
        _mm256_cmp_ps(x, lower_bound, _CMP_GE_OQ),
        _mm256_cmp_ps(x, zero, _CMP_LE_OQ));
    const __m256 safe_x = _mm256_blendv_ps(zero, x, valid);

    const __m256 n_float = _mm256_floor_ps(
        _mm256_add_ps(_mm256_mul_ps(safe_x, inv_ln2), half));
    const __m256 reduced = _mm256_sub_ps(
        _mm256_sub_ps(safe_x, _mm256_mul_ps(n_float, ln2_hi)),
        _mm256_mul_ps(n_float, ln2_lo));

    __m256 p = _mm256_set1_ps(1.0f / 40320.0f);
    p = _mm256_add_ps(_mm256_set1_ps(1.0f / 5040.0f), _mm256_mul_ps(reduced, p));
    p = _mm256_add_ps(_mm256_set1_ps(1.0f / 720.0f), _mm256_mul_ps(reduced, p));
    p = _mm256_add_ps(_mm256_set1_ps(1.0f / 120.0f), _mm256_mul_ps(reduced, p));
    p = _mm256_add_ps(_mm256_set1_ps(1.0f / 24.0f), _mm256_mul_ps(reduced, p));
    p = _mm256_add_ps(_mm256_set1_ps(1.0f / 6.0f), _mm256_mul_ps(reduced, p));
    p = _mm256_add_ps(half, _mm256_mul_ps(reduced, p));
    p = _mm256_add_ps(one, _mm256_mul_ps(reduced, p));
    p = _mm256_add_ps(one, _mm256_mul_ps(reduced, p));

    const __m256i exponent = _mm256_cvttps_epi32(n_float);
    const __m256i scale_bits = _mm256_slli_epi32(
        _mm256_add_epi32(exponent, _mm256_set1_epi32(127)), 23);
    const __m256 approximation = _mm256_mul_ps(_mm256_castsi256_ps(scale_bits), p);

    const int valid_lanes = _mm256_movemask_ps(valid);
    if (valid_lanes == 0xff)
        return approximation;

    float input_lanes[8];
    float result_lanes[8];
    _mm256_storeu_ps(input_lanes, x);
    _mm256_storeu_ps(result_lanes, approximation);
    for (int lane = 0; lane < 8; ++lane) {
        if ((valid_lanes & (1 << lane)) == 0)
            result_lanes[lane] = expf(input_lanes[lane]);
    }
    return _mm256_loadu_ps(result_lanes);
}

static inline __m256 log8_with_fallback(__m256 q) {
    const __m256 one = _mm256_set1_ps(1.0f);
    const __m256 half = _mm256_set1_ps(0.5f);
    const __m256 sqrt2 = _mm256_set1_ps(1.4142135623730951f);
    const __m256i mantissa_mask = _mm256_set1_epi32(0x007fffff);
    const __m256i exponent_mask = _mm256_set1_epi32(0x000000ff);

    const __m256i bits = _mm256_castps_si256(q);
    __m256i exponent = _mm256_sub_epi32(
        _mm256_and_si256(_mm256_srli_epi32(bits, 23), exponent_mask),
        _mm256_set1_epi32(127));
    __m256 mantissa = _mm256_castsi256_ps(_mm256_or_si256(
        _mm256_and_si256(bits, mantissa_mask), _mm256_set1_epi32(0x3f800000)));

    const __m256 reduce = _mm256_cmp_ps(mantissa, sqrt2, _CMP_GT_OQ);
    mantissa = _mm256_blendv_ps(mantissa, _mm256_mul_ps(mantissa, half), reduce);
    exponent = _mm256_add_epi32(exponent,
        _mm256_and_si256(_mm256_castps_si256(reduce), _mm256_set1_epi32(1)));

    const __m256 y = _mm256_div_ps(
        _mm256_sub_ps(mantissa, one), _mm256_add_ps(mantissa, one));
    const __m256 y2 = _mm256_mul_ps(y, y);
    __m256 p = _mm256_set1_ps(1.0f / 9.0f);
    p = _mm256_add_ps(_mm256_set1_ps(1.0f / 7.0f), _mm256_mul_ps(y2, p));
    p = _mm256_add_ps(_mm256_set1_ps(1.0f / 5.0f), _mm256_mul_ps(y2, p));
    p = _mm256_add_ps(_mm256_set1_ps(1.0f / 3.0f), _mm256_mul_ps(y2, p));
    p = _mm256_add_ps(one, _mm256_mul_ps(y2, p));

    const __m256 exponent_f = _mm256_cvtepi32_ps(exponent);
    const __m256 log_approx = _mm256_add_ps(
        _mm256_mul_ps(exponent_f, _mm256_set1_ps(0.6931471805599453f)),
        _mm256_mul_ps(_mm256_set1_ps(2.0f), _mm256_mul_ps(y, p)));

    float q_lanes[8];
    float log_lanes[8];
    _mm256_storeu_ps(q_lanes, q);
    _mm256_storeu_ps(log_lanes, log_approx);
    for (int lane = 0; lane < 8; ++lane) {
        if (!(q_lanes[lane] >= 1.0e-6f && q_lanes[lane] <= 1.0e6f))
            log_lanes[lane] = logf(q_lanes[lane]);
    }
    return _mm256_loadu_ps(log_lanes);
}

static inline __m256 CND8(__m256 X) {
    const __m256 zero = _mm256_setzero_ps();
    const __m256 one = _mm256_set1_ps(1.0f);
    const __m256 half = _mm256_set1_ps(0.5f);
    const __m256 sign_mask = _mm256_set1_ps(-0.0f);
    const __m256 L = _mm256_andnot_ps(sign_mask, X);

    const __m256 k = _mm256_div_ps(one, _mm256_add_ps(one, _mm256_mul_ps(_mm256_set1_ps(0.2316419f), L)));
    const __m256 k2 = _mm256_mul_ps(k, k);
    const __m256 k3 = _mm256_mul_ps(k2, k);
    const __m256 k4 = _mm256_mul_ps(k2, k2);
    const __m256 k5 = _mm256_mul_ps(k3, k2);

    __m256 w = _mm256_sub_ps(_mm256_mul_ps(_mm256_set1_ps(0.31938153f), k),
                             _mm256_mul_ps(_mm256_set1_ps(0.356563782f), k2));
    w = _mm256_add_ps(w, _mm256_mul_ps(_mm256_set1_ps(1.781477937f), k3));
    w = _mm256_add_ps(w, _mm256_mul_ps(_mm256_set1_ps(-1.821255978f), k4));
    w = _mm256_add_ps(w, _mm256_mul_ps(_mm256_set1_ps(1.330274429f), k5));

    const __m256 gaussian_arg = _mm256_mul_ps(
        _mm256_mul_ps(_mm256_sub_ps(zero, L), L), half);
    const __m256 gaussian = exp8_with_fallback(gaussian_arg);
    w = _mm256_mul_ps(w, _mm256_mul_ps(_mm256_set1_ps(0.39894228040f), gaussian));

    const __m256 positive = _mm256_cmp_ps(X, zero, _CMP_GT_OQ);
    const __m256 reflected = _mm256_sub_ps(one, w);
    return _mm256_or_ps(_mm256_and_ps(positive, reflected), _mm256_andnot_ps(positive, w));
}

static void black_scholes_avx8(float Sa[], float Xa[], float Ta[], float ra[], float va[], float result[], int count) {
    int i = 0;
    for (; i + 8 <= count; i += 8) {
        const __m256 S = _mm256_loadu_ps(Sa + i);
        const __m256 X = _mm256_loadu_ps(Xa + i);
        const __m256 T = _mm256_loadu_ps(Ta + i);
        const __m256 r = _mm256_loadu_ps(ra + i);
        const __m256 v = _mm256_loadu_ps(va + i);

        const __m256 ratio = _mm256_div_ps(S, X);
        const __m256 log_value = log8_with_fallback(ratio);
        const __m256 sqrt_T = _mm256_sqrt_ps(T);
        const __m256 drift = _mm256_mul_ps(
            _mm256_add_ps(r, _mm256_mul_ps(_mm256_mul_ps(v, v), _mm256_set1_ps(0.5f))), T);
        const __m256 d1 = _mm256_div_ps(
            _mm256_add_ps(log_value, drift), _mm256_mul_ps(v, sqrt_T));
        const __m256 d2 = _mm256_sub_ps(d1, _mm256_mul_ps(v, sqrt_T));

        const __m256 discount_arg = _mm256_mul_ps(
            _mm256_sub_ps(_mm256_setzero_ps(), r), T);
        const __m256 discount = exp8_with_fallback(discount_arg);

        const __m256 call_value = _mm256_mul_ps(S, CND8(d1));
        const __m256 put_value = _mm256_mul_ps(
            _mm256_mul_ps(X, discount), CND8(d2));
        _mm256_storeu_ps(result + i, _mm256_sub_ps(call_value, put_value));
    }

    if (i < count)
        black_scholes_serial(Sa + i, Xa + i, Ta + i, ra + i, va + i, result + i, count - i);
}
#endif

static inline void black_scholes_range(float Sa[], float Xa[], float Ta[], float ra[], float va[], float result[], int count) {
#if defined(__AVX2__)
    black_scholes_avx8(Sa, Xa, Ta, ra, va, result, count);
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

extern "C" void run(const void* input1, const void* input2, void* output, int n, int parameter, int threads) {
    if (n <= 0)
        return;

    float* a = (float*)input1;
    float* result = (float*)output;

    // Keep small jobs and single-worker calls free of OpenMP team setup.
    const int workers = (threads > 1 && n >= 2048)
        ? std::min(threads, n / 1024)
        : 1;

    if (workers <= 1) {
        black_scholes_range(a, a + n, a + 2 * n, a + 3 * n, a + 4 * n, result, n);
        return;
    }

#pragma omp parallel num_threads(workers)
    {
        const int tid = omp_get_thread_num();
        const int team_size = omp_get_num_threads();
        const int base = n / team_size;
        const int remainder = n % team_size;
        const int begin = tid * base + std::min(tid, remainder);
        const int count = base + (tid < remainder ? 1 : 0);

        black_scholes_range(a + begin, a + n + begin, a + 2 * n + begin,
                            a + 3 * n + begin, a + 4 * n + begin,
                            result + begin, count);
    }
}
