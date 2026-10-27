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
#include <cfloat>
#include <omp.h>

#if defined(__AVX__)
#include <immintrin.h>

// Vectorize CND's arithmetic while evaluating the exponential lane by lane.
static inline __m256 cnd8(__m256 x) {
    const __m256 sign_mask = _mm256_set1_ps(-0.0f);
    const __m256 zero = _mm256_setzero_ps();
    const __m256 one = _mm256_set1_ps(1.0f);
    __m256 magnitude = _mm256_andnot_ps(sign_mask, x);

    alignas(32) float magnitude_lanes[8];
    alignas(32) float exp_lanes[8];
    _mm256_store_ps(magnitude_lanes, magnitude);
    for (int lane = 0; lane < 8; ++lane)
        exp_lanes[lane] = expf(-magnitude_lanes[lane] * magnitude_lanes[lane] * .5f);
    const __m256 exp_value = _mm256_load_ps(exp_lanes);

    const __m256 k = _mm256_div_ps(
        one, _mm256_add_ps(one, _mm256_mul_ps(_mm256_set1_ps(0.2316419f), magnitude)));
    const __m256 k2 = _mm256_mul_ps(k, k);
    const __m256 k3 = _mm256_mul_ps(k2, k);
    const __m256 k4 = _mm256_mul_ps(k2, k2);
    const __m256 k5 = _mm256_mul_ps(k3, k2);

    __m256 w = _mm256_sub_ps(_mm256_mul_ps(_mm256_set1_ps(0.31938153f), k),
                             _mm256_mul_ps(_mm256_set1_ps(0.356563782f), k2));
    w = _mm256_add_ps(w, _mm256_mul_ps(_mm256_set1_ps(1.781477937f), k3));
    w = _mm256_add_ps(w, _mm256_mul_ps(_mm256_set1_ps(-1.821255978f), k4));
    w = _mm256_add_ps(w, _mm256_mul_ps(_mm256_set1_ps(1.330274429f), k5));
    w = _mm256_mul_ps(w, _mm256_mul_ps(_mm256_set1_ps(0.39894228040f), exp_value));

    const __m256 positive = _mm256_cmp_ps(x, zero, _CMP_GT_OQ);
    return _mm256_blendv_ps(w, _mm256_sub_ps(one, w), positive);
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

void black_scholes_serial(const float Sa[], const float Xa[], const float Ta[],
                          const float ra[], const float va[], float result[], int count) {
    for (int i = 0; i < count; ++i) {
        float S = Sa[i], X = Xa[i];
        float T = Ta[i], r = ra[i];
        float v = va[i];

        float d1 = (logf(S / X) + (r + v * v * .5f) * T) / (v * sqrtf(T));
        float d2 = d1 - v * sqrtf(T);

        result[i] = S * CND(d1) - X * expf(-r * T) * CND(d2);
    }
}

#if defined(__AVX__)
// One independently callable chunk for a threaded caller; no scheduling here.
static void black_scholes_avx(const float Sa[], const float Xa[], const float Ta[],
                              const float ra[], const float va[], float result[], int count) {
    int i = 0;
    for (; count - i >= 8; i += 8) {
        alignas(32) float log_ratio_lanes[8];
        alignas(32) float sqrt_t_lanes[8];
        alignas(32) float discount_lanes[8];
        for (int lane = 0; lane < 8; ++lane) {
            const int index = i + lane;
            const float t = Ta[index];
            const float r = ra[index];
            log_ratio_lanes[lane] = logf(Sa[index] / Xa[index]);
            sqrt_t_lanes[lane] = sqrtf(t);
            discount_lanes[lane] = expf(-r * t);
        }

        const __m256 s = _mm256_loadu_ps(Sa + i);
        const __m256 x = _mm256_loadu_ps(Xa + i);
        const __m256 t = _mm256_loadu_ps(Ta + i);
        const __m256 r = _mm256_loadu_ps(ra + i);
        const __m256 v = _mm256_loadu_ps(va + i);
        const __m256 log_ratio = _mm256_load_ps(log_ratio_lanes);
        const __m256 sqrt_t = _mm256_load_ps(sqrt_t_lanes);
        const __m256 discount = _mm256_load_ps(discount_lanes);

        const __m256 half_v_squared = _mm256_mul_ps(
            _mm256_mul_ps(v, v), _mm256_set1_ps(.5f));
        const __m256 rate_and_variance = _mm256_add_ps(r, half_v_squared);
        const __m256 numerator = _mm256_add_ps(
            log_ratio, _mm256_mul_ps(rate_and_variance, t));
        const __m256 denominator = _mm256_mul_ps(v, sqrt_t);
        const __m256 d1 = _mm256_div_ps(numerator, denominator);
        const __m256 d2 = _mm256_sub_ps(d1, denominator);

        const __m256 cnd_d1 = cnd8(d1);
        const __m256 cnd_d2 = cnd8(d2);
        const __m256 price = _mm256_sub_ps(
            _mm256_mul_ps(s, cnd_d1),
            _mm256_mul_ps(_mm256_mul_ps(x, discount), cnd_d2));
        _mm256_storeu_ps(result + i, price);
    }

    // Scalar tail handles every n, including chunks not divisible by eight.
    for (; i < count; ++i) {
        const float S = Sa[i], X = Xa[i];
        const float T = Ta[i], r = ra[i], v = va[i];
        const float d1 = (logf(S / X) + (r + v * v * .5f) * T) / (v * sqrtf(T));
        const float d2 = d1 - v * sqrtf(T);
        result[i] = S * CND(d1) - X * expf(-r * T) * CND(d2);
    }
}
#endif

#if defined(__AVX2__)
// Fast range-reduced SIMD math for the common finite inputs. Unusual lanes
// retain the scalar libm result, rather than relying on polynomial edge cases.
static inline __m256 fast_log8(__m256 x) {
    const __m256i bits = _mm256_castps_si256(x);
    __m256i exponent = _mm256_and_si256(
        _mm256_srli_epi32(bits, 23), _mm256_set1_epi32(0xff));
    exponent = _mm256_sub_epi32(exponent, _mm256_set1_epi32(127));

    const __m256 mantissa = _mm256_castsi256_ps(_mm256_or_si256(
        _mm256_and_si256(bits, _mm256_set1_epi32(0x007fffff)),
        _mm256_set1_epi32(0x3f800000)));
    const __m256 adjust = _mm256_cmp_ps(
        mantissa, _mm256_set1_ps(1.41421356237f), _CMP_GT_OQ);
    const __m256 reduced_mantissa = _mm256_blendv_ps(
        mantissa, _mm256_mul_ps(mantissa, _mm256_set1_ps(.5f)), adjust);
    exponent = _mm256_add_epi32(exponent, _mm256_and_si256(
        _mm256_castps_si256(adjust), _mm256_set1_epi32(1)));

    const __m256 one = _mm256_set1_ps(1.0f);
    const __m256 z = _mm256_div_ps(
        _mm256_sub_ps(reduced_mantissa, one),
        _mm256_add_ps(reduced_mantissa, one));
    const __m256 z2 = _mm256_mul_ps(z, z);
    __m256 series = _mm256_set1_ps(1.0f / 11.0f);
    series = _mm256_add_ps(_mm256_set1_ps(1.0f / 9.0f), _mm256_mul_ps(z2, series));
    series = _mm256_add_ps(_mm256_set1_ps(1.0f / 7.0f), _mm256_mul_ps(z2, series));
    series = _mm256_add_ps(_mm256_set1_ps(1.0f / 5.0f), _mm256_mul_ps(z2, series));
    series = _mm256_add_ps(_mm256_set1_ps(1.0f / 3.0f), _mm256_mul_ps(z2, series));
    const __m256 log_mantissa = _mm256_mul_ps(
        _mm256_set1_ps(2.0f), _mm256_mul_ps(z, _mm256_add_ps(one, _mm256_mul_ps(z2, series))));
    const __m256 exponent_f = _mm256_cvtepi32_ps(exponent);
    __m256 result = _mm256_add_ps(
        log_mantissa, _mm256_mul_ps(exponent_f, _mm256_set1_ps(0.693145751953125f)));
    result = _mm256_add_ps(
        result, _mm256_mul_ps(exponent_f, _mm256_set1_ps(1.428606765330187e-6f)));

    const __m256 valid = _mm256_and_ps(
        _mm256_cmp_ps(x, _mm256_set1_ps(FLT_MIN), _CMP_GE_OQ),
        _mm256_cmp_ps(x, _mm256_set1_ps(FLT_MAX), _CMP_LE_OQ));
    const int valid_mask = _mm256_movemask_ps(valid);
    if (valid_mask != 0xff) {
        alignas(32) float input_lanes[8];
        alignas(32) float result_lanes[8];
        _mm256_store_ps(input_lanes, x);
        _mm256_store_ps(result_lanes, result);
        for (int lane = 0; lane < 8; ++lane) {
            if ((valid_mask & (1 << lane)) == 0)
                result_lanes[lane] = logf(input_lanes[lane]);
        }
        result = _mm256_load_ps(result_lanes);
    }
    return result;
}

static inline __m256 fast_exp8(__m256 x) {
    const __m256 lower = _mm256_set1_ps(-80.0f);
    const __m256 upper = _mm256_set1_ps(80.0f);
    const __m256 valid = _mm256_and_ps(
        _mm256_cmp_ps(x, lower, _CMP_GE_OQ),
        _mm256_cmp_ps(x, upper, _CMP_LE_OQ));
    const int valid_mask = _mm256_movemask_ps(valid);

    // Clamp only the polynomial's work value; out-of-range lanes are replaced
    // below with expf evaluated on their original inputs.
    const __m256 bounded = _mm256_min_ps(_mm256_max_ps(x, lower), upper);
    const __m256 scaled = _mm256_mul_ps(bounded, _mm256_set1_ps(1.4426950408889634f));
    const __m256 rounded = _mm256_round_ps(
        scaled, _MM_FROUND_TO_NEAREST_INT | _MM_FROUND_NO_EXC);
    const __m256i exponent = _mm256_cvttps_epi32(rounded);
    const __m256 exponent_f = _mm256_cvtepi32_ps(exponent);

    const __m256 reduced = _mm256_sub_ps(
        _mm256_sub_ps(bounded, _mm256_mul_ps(exponent_f, _mm256_set1_ps(0.693145751953125f))),
        _mm256_mul_ps(exponent_f, _mm256_set1_ps(1.428606765330187e-6f)));
    __m256 polynomial = _mm256_set1_ps(1.0f / 40320.0f);
    polynomial = _mm256_add_ps(_mm256_set1_ps(1.0f / 5040.0f), _mm256_mul_ps(reduced, polynomial));
    polynomial = _mm256_add_ps(_mm256_set1_ps(1.0f / 720.0f), _mm256_mul_ps(reduced, polynomial));
    polynomial = _mm256_add_ps(_mm256_set1_ps(1.0f / 120.0f), _mm256_mul_ps(reduced, polynomial));
    polynomial = _mm256_add_ps(_mm256_set1_ps(1.0f / 24.0f), _mm256_mul_ps(reduced, polynomial));
    polynomial = _mm256_add_ps(_mm256_set1_ps(1.0f / 6.0f), _mm256_mul_ps(reduced, polynomial));
    polynomial = _mm256_add_ps(_mm256_set1_ps(.5f), _mm256_mul_ps(reduced, polynomial));
    polynomial = _mm256_add_ps(_mm256_set1_ps(1.0f), _mm256_mul_ps(reduced, polynomial));
    polynomial = _mm256_add_ps(_mm256_set1_ps(1.0f), _mm256_mul_ps(reduced, polynomial));

    const __m256i power_bits = _mm256_slli_epi32(
        _mm256_add_epi32(exponent, _mm256_set1_epi32(127)), 23);
    __m256 result = _mm256_mul_ps(polynomial, _mm256_castsi256_ps(power_bits));
    if (valid_mask != 0xff) {
        alignas(32) float input_lanes[8];
        alignas(32) float result_lanes[8];
        _mm256_store_ps(input_lanes, x);
        _mm256_store_ps(result_lanes, result);
        for (int lane = 0; lane < 8; ++lane) {
            if ((valid_mask & (1 << lane)) == 0)
                result_lanes[lane] = expf(input_lanes[lane]);
        }
        result = _mm256_load_ps(result_lanes);
    }
    return result;
}

static inline __m256 cnd8_fast_math(__m256 x) {
    const __m256 zero = _mm256_setzero_ps();
    const __m256 one = _mm256_set1_ps(1.0f);
    const __m256 magnitude = _mm256_andnot_ps(_mm256_set1_ps(-0.0f), x);
    const __m256 exp_argument = _mm256_mul_ps(
        _mm256_mul_ps(_mm256_sub_ps(zero, magnitude), magnitude),
        _mm256_set1_ps(.5f));
    const __m256 exp_value = fast_exp8(exp_argument);

    const __m256 k = _mm256_div_ps(
        one, _mm256_add_ps(one, _mm256_mul_ps(_mm256_set1_ps(0.2316419f), magnitude)));
    const __m256 k2 = _mm256_mul_ps(k, k);
    const __m256 k3 = _mm256_mul_ps(k2, k);
    const __m256 k4 = _mm256_mul_ps(k2, k2);
    const __m256 k5 = _mm256_mul_ps(k3, k2);

    __m256 w = _mm256_sub_ps(_mm256_mul_ps(_mm256_set1_ps(0.31938153f), k),
                             _mm256_mul_ps(_mm256_set1_ps(0.356563782f), k2));
    w = _mm256_add_ps(w, _mm256_mul_ps(_mm256_set1_ps(1.781477937f), k3));
    w = _mm256_add_ps(w, _mm256_mul_ps(_mm256_set1_ps(-1.821255978f), k4));
    w = _mm256_add_ps(w, _mm256_mul_ps(_mm256_set1_ps(1.330274429f), k5));
    w = _mm256_mul_ps(w, _mm256_mul_ps(_mm256_set1_ps(0.39894228040f), exp_value));

    const __m256 positive = _mm256_cmp_ps(x, zero, _CMP_GT_OQ);
    return _mm256_blendv_ps(w, _mm256_sub_ps(one, w), positive);
}

// Per-thread AVX2 chunk: no scheduling, alignment promises, or vector-libm ABI.
static void black_scholes_avx2_fast_math(const float Sa[], const float Xa[], const float Ta[],
                                          const float ra[], const float va[], float result[], int count) {
    int i = 0;
    for (; count - i >= 8; i += 8) {
        const __m256 s = _mm256_loadu_ps(Sa + i);
        const __m256 x = _mm256_loadu_ps(Xa + i);
        const __m256 t = _mm256_loadu_ps(Ta + i);
        const __m256 r = _mm256_loadu_ps(ra + i);
        const __m256 v = _mm256_loadu_ps(va + i);
        const __m256 log_ratio = fast_log8(_mm256_div_ps(s, x));
        const __m256 sqrt_t = _mm256_sqrt_ps(t);
        const __m256 discount = fast_exp8(_mm256_mul_ps(_mm256_sub_ps(
            _mm256_setzero_ps(), r), t));

        const __m256 half_v_squared = _mm256_mul_ps(
            _mm256_mul_ps(v, v), _mm256_set1_ps(.5f));
        const __m256 rate_and_variance = _mm256_add_ps(r, half_v_squared);
        const __m256 numerator = _mm256_add_ps(
            log_ratio, _mm256_mul_ps(rate_and_variance, t));
        const __m256 denominator = _mm256_mul_ps(v, sqrt_t);
        const __m256 d1 = _mm256_div_ps(numerator, denominator);
        const __m256 d2 = _mm256_sub_ps(d1, denominator);

        const __m256 cnd_d1 = cnd8_fast_math(d1);
        const __m256 cnd_d2 = cnd8_fast_math(d2);
        const __m256 price = _mm256_sub_ps(
            _mm256_mul_ps(s, cnd_d1),
            _mm256_mul_ps(_mm256_mul_ps(x, discount), cnd_d2));
        _mm256_storeu_ps(result + i, price);
    }

    for (; i < count; ++i) {
        const float S = Sa[i], X = Xa[i];
        const float T = Ta[i], r = ra[i], v = va[i];
        const float d1 = (logf(S / X) + (r + v * v * .5f) * T) / (v * sqrtf(T));
        const float d2 = d1 - v * sqrtf(T);
        result[i] = S * CND(d1) - X * expf(-r * T) * CND(d2);
    }
}
#endif

static inline void black_scholes_chunk(const float Sa[], const float Xa[], const float Ta[],
                                       const float ra[], const float va[], float result[], int count) {
#if defined(__AVX2__)
    black_scholes_avx2_fast_math(Sa, Xa, Ta, ra, va, result, count);
#elif defined(__AVX__)
    black_scholes_avx(Sa, Xa, Ta, ra, va, result, count);
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

extern "C" void run(const void* input1, const void*, void* output, int n, int, int threads) {
    if (n <= 0)
        return;

    const float* S = static_cast<const float*>(input1);
    const float* X = S + n;
    const float* T = X + n;
    const float* r = T + n;
    const float* v = r + n;
    float* result = static_cast<float*>(output);

    // Division/remainder avoids overflowing n + 7 for large valid int sizes.
    const int block_count = n / 8 + ((n % 8) != 0);
    const int thread_count = threads > 0 ? threads : 1;

    // Avoid creating a team when there is no parallel work to distribute.
    if (block_count == 1 || thread_count == 1) {
        black_scholes_chunk(S, X, T, r, v, result, n);
        return;
    }

    // Each static block owns eight consecutive elements; the last is bounded.
    #pragma omp parallel for schedule(static) num_threads(thread_count)
    for (int block = 0; block < block_count; ++block) {
        const int begin = block * 8;
        const int remaining = n - begin;
        const int count = remaining < 8 ? remaining : 8;
        black_scholes_chunk(S + begin, X + begin, T + begin,
                            r + begin, v + begin, result + begin, count);
    }
}
