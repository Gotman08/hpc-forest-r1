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
    // This remains a scalar-expression implementation on targets where the
    // explicit AVX2 kernel below is not enabled. The SIMD directive does not
    // introduce thread scheduling.
    #pragma omp simd
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
// Fast exponential for non-positive inputs, used only for exp(-L*L/2) in CND
// and for discount factors when every lane has a non-positive exponent.
static inline __m256 exp_nonpositive_avx2(__m256 x) {
    const __m256 underflow_limit = _mm256_set1_ps(-103.97208f);
    const __m256 in_range = _mm256_cmp_ps(x, underflow_limit, _CMP_GT_OQ);
    const __m256 safe_x = _mm256_max_ps(x, underflow_limit);

    const __m256 log2e = _mm256_set1_ps(1.4426950408889634f);
    const __m256 ln2 = _mm256_set1_ps(0.6931471805599453f);
    const __m256 rounded_n = _mm256_floor_ps(
        _mm256_add_ps(_mm256_mul_ps(safe_x, log2e), _mm256_set1_ps(0.5f)));
    __m256i n = _mm256_cvtps_epi32(rounded_n);
    n = _mm256_max_epi32(n, _mm256_set1_epi32(-149));
    const __m256 nf = _mm256_cvtepi32_ps(n);
    const __m256 r = _mm256_sub_ps(safe_x, _mm256_mul_ps(nf, ln2));

    __m256 p = _mm256_set1_ps(1.0f / 5040.0f);
    p = _mm256_add_ps(_mm256_mul_ps(p, r), _mm256_set1_ps(1.0f / 720.0f));
    p = _mm256_add_ps(_mm256_mul_ps(p, r), _mm256_set1_ps(1.0f / 120.0f));
    p = _mm256_add_ps(_mm256_mul_ps(p, r), _mm256_set1_ps(1.0f / 24.0f));
    p = _mm256_add_ps(_mm256_mul_ps(p, r), _mm256_set1_ps(1.0f / 6.0f));
    p = _mm256_add_ps(_mm256_mul_ps(p, r), _mm256_set1_ps(0.5f));
    p = _mm256_add_ps(_mm256_mul_ps(p, r), _mm256_set1_ps(1.0f));
    p = _mm256_add_ps(_mm256_mul_ps(p, r), _mm256_set1_ps(1.0f));

    const __m256i normal_mask = _mm256_cmpgt_epi32(n, _mm256_set1_epi32(-127));
    const __m256i normal_bits = _mm256_slli_epi32(
        _mm256_add_epi32(n, _mm256_set1_epi32(127)), 23);
    const __m256i subnormal_shift = _mm256_add_epi32(n, _mm256_set1_epi32(149));
    const __m256i subnormal_bits = _mm256_sllv_epi32(
        _mm256_set1_epi32(1), subnormal_shift);
    const __m256i scale_bits = _mm256_blendv_epi8(
        subnormal_bits, normal_bits, normal_mask);
    const __m256 scale = _mm256_castsi256_ps(scale_bits);
    const __m256 result = _mm256_mul_ps(p, scale);
    return _mm256_and_ps(result, in_range);
}

// One Newton step refines the AVX2 reciprocal estimate for safe, finite
// denominators. Callers retain exact division for unusual denominator lanes.
static inline __m256 reciprocal_refined_avx2(__m256 x) {
    const __m256 estimate = _mm256_rcp_ps(x);
    const __m256 correction = _mm256_sub_ps(
        _mm256_set1_ps(2.0f), _mm256_mul_ps(x, estimate));
    return _mm256_mul_ps(estimate, correction);
}

static inline __m256 divide_refined_avx2(__m256 numerator, __m256 denominator) {
    const __m256 sign_mask = _mm256_set1_ps(-0.0f);
    const __m256 abs_denominator = _mm256_andnot_ps(sign_mask, denominator);
    const __m256 safe = _mm256_and_ps(
        _mm256_cmp_ps(abs_denominator, _mm256_set1_ps(1.175494351e-38f), _CMP_GE_OQ),
        _mm256_cmp_ps(abs_denominator, _mm256_set1_ps(1.0e30f), _CMP_LE_OQ));
    if (_mm256_movemask_ps(safe) == 0xff)
        return _mm256_mul_ps(numerator, reciprocal_refined_avx2(denominator));
    return _mm256_div_ps(numerator, denominator);
}

// Approximate log for positive, normal inputs. The caller masks exceptional
// and numerically sensitive lanes and computes those with scalar logf instead.
static inline __m256 log_positive_normal_avx2(__m256 x) {
    const __m256i bits = _mm256_castps_si256(x);
    __m256i exponent = _mm256_sub_epi32(
        _mm256_and_si256(_mm256_srli_epi32(bits, 23), _mm256_set1_epi32(0xff)),
        _mm256_set1_epi32(127));
    const __m256i mantissa_bits = _mm256_or_si256(
        _mm256_and_si256(bits, _mm256_set1_epi32(0x007fffff)),
        _mm256_set1_epi32(0x3f800000));
    __m256 mantissa = _mm256_castsi256_ps(mantissa_bits);

    const __m256 adjust = _mm256_cmp_ps(
        mantissa, _mm256_set1_ps(1.41421356237f), _CMP_GT_OQ);
    mantissa = _mm256_blendv_ps(
        mantissa, _mm256_mul_ps(mantissa, _mm256_set1_ps(0.5f)), adjust);
    exponent = _mm256_add_epi32(
        exponent, _mm256_and_si256(_mm256_castps_si256(adjust), _mm256_set1_epi32(1)));

    const __m256 z = _mm256_mul_ps(
        _mm256_sub_ps(mantissa, _mm256_set1_ps(1.0f)),
        reciprocal_refined_avx2(_mm256_add_ps(mantissa, _mm256_set1_ps(1.0f))));
    const __m256 z2 = _mm256_mul_ps(z, z);
    __m256 p = _mm256_set1_ps(1.0f / 11.0f);
    p = _mm256_add_ps(_mm256_mul_ps(p, z2), _mm256_set1_ps(1.0f / 9.0f));
    p = _mm256_add_ps(_mm256_mul_ps(p, z2), _mm256_set1_ps(1.0f / 7.0f));
    p = _mm256_add_ps(_mm256_mul_ps(p, z2), _mm256_set1_ps(1.0f / 5.0f));
    p = _mm256_add_ps(_mm256_mul_ps(p, z2), _mm256_set1_ps(1.0f / 3.0f));
    const __m256 log_mantissa = _mm256_mul_ps(
        _mm256_mul_ps(_mm256_set1_ps(2.0f), z),
        _mm256_add_ps(_mm256_set1_ps(1.0f), _mm256_mul_ps(z2, p)));
    return _mm256_add_ps(
        log_mantissa,
        _mm256_mul_ps(_mm256_cvtepi32_ps(exponent),
                      _mm256_set1_ps(0.6931471805599453f)));
}

static inline __m256 cnd_avx2(__m256 x) {
    const __m256 sign_mask = _mm256_set1_ps(-0.0f);
    const __m256 L = _mm256_andnot_ps(sign_mask, x);
    const __m256 one = _mm256_set1_ps(1.0f);
    const __m256 k = divide_refined_avx2(
        one, _mm256_add_ps(one, _mm256_mul_ps(_mm256_set1_ps(0.2316419f), L)));
    const __m256 k2 = _mm256_mul_ps(k, k);

    __m256 tail = _mm256_add_ps(
        _mm256_set1_ps(-1.821255978f),
        _mm256_mul_ps(_mm256_set1_ps(1.330274429f), k));
    tail = _mm256_add_ps(
        _mm256_set1_ps(1.781477937f), _mm256_mul_ps(k, tail));
    tail = _mm256_add_ps(
        _mm256_set1_ps(-0.356563782f), _mm256_mul_ps(k, tail));
    __m256 w = _mm256_add_ps(
        _mm256_mul_ps(_mm256_set1_ps(0.31938153f), k),
        _mm256_mul_ps(k2, tail));

    const __m256 exponent = _mm256_mul_ps(_mm256_mul_ps(L, L), _mm256_set1_ps(-0.5f));
    const __m256 normal_density = _mm256_mul_ps(
        _mm256_set1_ps(0.39894228040f), exp_nonpositive_avx2(exponent));
    w = _mm256_mul_ps(w, normal_density);

    const __m256 positive = _mm256_cmp_ps(x, _mm256_setzero_ps(), _CMP_GT_OQ);
    return _mm256_blendv_ps(w, _mm256_sub_ps(one, w), positive);
}
#endif

// A range entry point suitable for a caller to use on an individual thread's
// [first, last) partition. It deliberately performs no thread scheduling.
static void black_scholes_simd_range(float Sa[], float Xa[], float Ta[], float ra[],
                                     float va[], float result[], int first, int last) {
    int i = first;
#if defined(__AVX2__)
    for (; last - i >= 8; i += 8) {
        const __m256 S = _mm256_loadu_ps(Sa + i);
        const __m256 X = _mm256_loadu_ps(Xa + i);
        const __m256 T = _mm256_loadu_ps(Ta + i);
        const __m256 r = _mm256_loadu_ps(ra + i);
        const __m256 v = _mm256_loadu_ps(va + i);

        const __m256 sqrt_t = _mm256_sqrt_ps(T);
        const __m256 vsqrt_t = _mm256_mul_ps(v, sqrt_t);
        const __m256 ratio = _mm256_div_ps(S, X);
        const __m256 sign_mask = _mm256_set1_ps(-0.0f);
        const __m256 abs_vsqrt_t = _mm256_andnot_ps(sign_mask, vsqrt_t);
        const __m256 ratio_normal = _mm256_and_ps(
            _mm256_cmp_ps(ratio, _mm256_set1_ps(1.175494351e-38f), _CMP_GE_OQ),
            _mm256_cmp_ps(ratio, _mm256_set1_ps(INFINITY), _CMP_LT_OQ));
        const __m256 stable_scale = _mm256_and_ps(
            _mm256_cmp_ps(abs_vsqrt_t, _mm256_set1_ps(1.0e-2f), _CMP_GE_OQ),
            _mm256_cmp_ps(abs_vsqrt_t, _mm256_set1_ps(INFINITY), _CMP_LT_OQ));
        const __m256 log_valid = _mm256_and_ps(ratio_normal, stable_scale);
        const __m256 safe_ratio = _mm256_blendv_ps(
            _mm256_set1_ps(1.0f), ratio, log_valid);
        const __m256 fast_log = log_positive_normal_avx2(safe_ratio);

        alignas(32) float s_lanes[8];
        alignas(32) float x_lanes[8];
        alignas(32) float t_lanes[8];
        alignas(32) float r_lanes[8];
        alignas(32) float ratio_lanes[8];
        alignas(32) float log_lanes[8];
        alignas(32) float fast_log_lanes[8];
        alignas(32) float discount_lanes[8];
        _mm256_store_ps(t_lanes, T);
        _mm256_store_ps(r_lanes, r);
        _mm256_store_ps(ratio_lanes, ratio);
        const int log_valid_mask = _mm256_movemask_ps(log_valid);
        if (log_valid_mask == 0xff) {
            _mm256_store_ps(log_lanes, fast_log);
        } else {
            _mm256_store_ps(s_lanes, S);
            _mm256_store_ps(x_lanes, X);
            _mm256_store_ps(fast_log_lanes, fast_log);
            for (int lane = 0; lane < 8; ++lane) {
                if (log_valid_mask & (1 << lane))
                    log_lanes[lane] = fast_log_lanes[lane];
                else
                    log_lanes[lane] = logf(s_lanes[lane] / x_lanes[lane]);
            }
        }

        const __m256 discount_exponent = _mm256_mul_ps(
            _mm256_sub_ps(_mm256_setzero_ps(), r), T);
        if (_mm256_movemask_ps(_mm256_cmp_ps(
                discount_exponent, _mm256_setzero_ps(), _CMP_LE_OQ)) == 0xff) {
            _mm256_store_ps(discount_lanes, exp_nonpositive_avx2(discount_exponent));
        } else {
            for (int lane = 0; lane < 8; ++lane)
                discount_lanes[lane] = expf(-r_lanes[lane] * t_lanes[lane]);
        }

        const __m256 log_ratio = _mm256_load_ps(log_lanes);
        const __m256 drift = _mm256_add_ps(
            r, _mm256_mul_ps(_mm256_mul_ps(v, v), _mm256_set1_ps(0.5f)));
        const __m256 d1 = divide_refined_avx2(
            _mm256_add_ps(log_ratio, _mm256_mul_ps(drift, T)), vsqrt_t);
        const __m256 d2 = _mm256_sub_ps(d1, vsqrt_t);

        const __m256 call_value = _mm256_mul_ps(S, cnd_avx2(d1));
        const __m256 put_value = _mm256_mul_ps(
            _mm256_mul_ps(X, _mm256_load_ps(discount_lanes)), cnd_avx2(d2));
        _mm256_storeu_ps(result + i, _mm256_sub_ps(call_value, put_value));
    }
#endif
    for (; i < last; ++i) {
        const float S = Sa[i], X = Xa[i];
        const float T = Ta[i], r = ra[i];
        const float v = va[i];
        const float d1 = (logf(S / X) + (r + v * v * .5f) * T) / (v * sqrtf(T));
        const float d2 = d1 - v * sqrtf(T);
        result[i] = S * CND(d1) - X * expf(-r * T) * CND(d2);
    }
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

extern "C" void run(const void* input1, const void* input2, void* output,
                     int n, int parameter, int threads) {
    float* a = (float*)input1;
    float* result = (float*)output;

    if (threads <= 1 || n <= 1) {
        black_scholes_simd_range(a, a + n, a + 2 * n, a + 3 * n, a + 4 * n,
                                 result, 0, n);
        return;
    }

    const int team_size = std::min(threads, n);
#pragma omp parallel for schedule(static) num_threads(team_size)
    for (int partition = 0; partition < team_size; ++partition) {
        const int first = static_cast<int>(
            (static_cast<std::int64_t>(n) * partition) / team_size);
        const int last = static_cast<int>(
            (static_cast<std::int64_t>(n) * (partition + 1)) / team_size);
        black_scholes_simd_range(a, a + n, a + 2 * n, a + 3 * n, a + 4 * n,
                                 result, first, last);
    }
}
