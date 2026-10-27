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

#if defined(__GNUC__) || defined(__clang__)
#if defined(__x86_64__) || defined(__i386__)
#include <immintrin.h>
#define BS_HAS_AVX2_DISPATCH 1
#define BS_TARGET_AVX2 __attribute__((target("avx2")))
#define BS_TARGET_AVX2_FMA __attribute__((target("avx2,fma")))
#else
#define BS_HAS_AVX2_DISPATCH 0
#endif
#else
#define BS_HAS_AVX2_DISPATCH 0
#endif

// Cumulative normal distribution function, using Gm3's FMA Horner chain.
#if defined(_OPENMP)
#pragma omp declare simd
#endif
static inline float CND(float X) {
    float L = fabsf(X);
    float k = 1.f / (1.f + 0.2316419f * L);

    const float invSqrt2Pi = 0.39894228040f;
    float w = fmaf(1.330274429f, k, -1.821255978f);
    w = fmaf(w, k, 1.781477937f);
    w = fmaf(w, k, -0.356563782f);
    w = fmaf(w, k, 0.31938153f);
    w *= k;
    w *= invSqrt2Pi * expf(-L * L * .5f);

    if (X > 0.f)
        w = 1.f - w;
    return w;
}

static inline float black_scholes_value(float S, float X, float T, float r, float v) {
    float d1 = (logf(S / X) + (r + v * v * .5f) * T) / (v * sqrtf(T));
    float d2 = d1 - v * sqrtf(T);
    return S * CND(d1) - X * expf(-r * T) * CND(d2);
}

#if BS_HAS_AVX2_DISPATCH
// Range-reduced AVX2 exponential; out-of-range lanes use exact scalar expf.
static BS_TARGET_AVX2 inline __m256 exp_avx2(__m256 x) {
    const __m256 lower = _mm256_set1_ps(-80.f);
    const __m256 upper = _mm256_set1_ps(80.f);
    const __m256 in_range = _mm256_and_ps(
        _mm256_cmp_ps(x, lower, _CMP_GE_OQ),
        _mm256_cmp_ps(x, upper, _CMP_LE_OQ));
    const int valid_mask = _mm256_movemask_ps(in_range);

    // Keep the approximation inputs safe for lanes whose exact expf result
    // will replace the approximation below.
    __m256 safe_x = x;
    if (valid_mask != 0xff)
        safe_x = _mm256_blendv_ps(_mm256_setzero_ps(), x, in_range);

    const __m256 log2e = _mm256_set1_ps(1.4426950408889634f);
    const __m256 scaled = _mm256_mul_ps(safe_x, log2e);
    const __m256 rounded = _mm256_round_ps(
        scaled, _MM_FROUND_TO_NEAREST_INT | _MM_FROUND_NO_EXC);
    const __m256i n = _mm256_cvttps_epi32(rounded);
    const __m256 nf = _mm256_cvtepi32_ps(n);

    // Split ln(2) reduces cancellation in x - n*ln(2).
    const __m256 ln2_hi = _mm256_set1_ps(0.693145751953125f);
    const __m256 ln2_lo = _mm256_set1_ps(1.428606765330187e-6f);
    const __m256 reduced = _mm256_sub_ps(
        _mm256_sub_ps(safe_x, _mm256_mul_ps(nf, ln2_hi)),
        _mm256_mul_ps(nf, ln2_lo));

    // Degree-eight Taylor polynomial on [-ln(2)/2, ln(2)/2].
    __m256 p = _mm256_set1_ps(1.f / 40320.f);
    p = _mm256_add_ps(_mm256_mul_ps(p, reduced), _mm256_set1_ps(1.f / 5040.f));
    p = _mm256_add_ps(_mm256_mul_ps(p, reduced), _mm256_set1_ps(1.f / 720.f));
    p = _mm256_add_ps(_mm256_mul_ps(p, reduced), _mm256_set1_ps(1.f / 120.f));
    p = _mm256_add_ps(_mm256_mul_ps(p, reduced), _mm256_set1_ps(1.f / 24.f));
    p = _mm256_add_ps(_mm256_mul_ps(p, reduced), _mm256_set1_ps(1.f / 6.f));
    p = _mm256_add_ps(_mm256_mul_ps(p, reduced), _mm256_set1_ps(0.5f));
    p = _mm256_add_ps(_mm256_mul_ps(p, reduced), _mm256_set1_ps(1.f));
    p = _mm256_add_ps(_mm256_mul_ps(p, reduced), _mm256_set1_ps(1.f));

    // All n values for x in [-80, 80] produce normal powers of two.
    const __m256i exponent = _mm256_slli_epi32(
        _mm256_add_epi32(n, _mm256_set1_epi32(127)), 23);
    const __m256 scale = _mm256_castsi256_ps(exponent);
    __m256 result = _mm256_mul_ps(p, scale);

    if (valid_mask != 0xff) {
        float x_lanes[8];
        float result_lanes[8];
        _mm256_storeu_ps(x_lanes, x);
        _mm256_storeu_ps(result_lanes, result);
        for (int lane = 0; lane < 8; ++lane) {
            if ((valid_mask & (1 << lane)) == 0)
                result_lanes[lane] = expf(x_lanes[lane]);
        }
        result = _mm256_loadu_ps(result_lanes);
    }
    return result;
}

// Approximate log for ordinary positive ratios; use exact logf only for
// lanes outside the approximation interval.
static BS_TARGET_AVX2 inline __m256 log_ratio_avx2(__m256 ratio) {
    const __m256 lower = _mm256_set1_ps(2.3283064365386963e-10f); // 2^-32
    const __m256 upper = _mm256_set1_ps(4294967296.f);             // 2^32
    const __m256 in_range = _mm256_and_ps(
        _mm256_cmp_ps(ratio, lower, _CMP_GE_OQ),
        _mm256_cmp_ps(ratio, upper, _CMP_LE_OQ));
    const int valid_mask = _mm256_movemask_ps(in_range);

    // A neutral positive value keeps the vector approximation well-defined
    // for lanes whose result will be replaced by scalar logf.
    __m256 safe_ratio = ratio;
    if (valid_mask != 0xff)
        safe_ratio = _mm256_blendv_ps(_mm256_set1_ps(1.f), ratio, in_range);

    const __m256i bits = _mm256_castps_si256(safe_ratio);
    const __m256i exponent_bits = _mm256_and_si256(
        _mm256_srli_epi32(bits, 23), _mm256_set1_epi32(0xff));
    __m256i exponent = _mm256_sub_epi32(exponent_bits, _mm256_set1_epi32(127));
    const __m256i mantissa_bits = _mm256_or_si256(
        _mm256_and_si256(bits, _mm256_set1_epi32(0x007fffff)),
        _mm256_set1_epi32(0x3f800000));
    __m256 mantissa = _mm256_castsi256_ps(mantissa_bits);

    // Reduce mantissa to [1, sqrt(2)] for a rapidly converging atanh series.
    const __m256 reduce = _mm256_cmp_ps(
        mantissa, _mm256_set1_ps(1.4142135623730951f), _CMP_GT_OQ);
    const __m256i adjust = _mm256_and_si256(
        _mm256_castps_si256(reduce), _mm256_set1_epi32(1));
    exponent = _mm256_add_epi32(exponent, adjust);
    mantissa = _mm256_blendv_ps(
        mantissa, _mm256_mul_ps(mantissa, _mm256_set1_ps(0.5f)), reduce);

    const __m256 z = _mm256_div_ps(
        _mm256_sub_ps(mantissa, _mm256_set1_ps(1.f)),
        _mm256_add_ps(mantissa, _mm256_set1_ps(1.f)));
    const __m256 z2 = _mm256_mul_ps(z, z);
    __m256 p = _mm256_set1_ps(1.f / 11.f);
    p = _mm256_add_ps(_mm256_mul_ps(p, z2), _mm256_set1_ps(1.f / 9.f));
    p = _mm256_add_ps(_mm256_mul_ps(p, z2), _mm256_set1_ps(1.f / 7.f));
    p = _mm256_add_ps(_mm256_mul_ps(p, z2), _mm256_set1_ps(1.f / 5.f));
    p = _mm256_add_ps(_mm256_mul_ps(p, z2), _mm256_set1_ps(1.f / 3.f));
    p = _mm256_add_ps(_mm256_mul_ps(p, z2), _mm256_set1_ps(1.f));
    const __m256 log_mantissa = _mm256_mul_ps(
        _mm256_mul_ps(_mm256_set1_ps(2.f), z), p);
    const __m256 log_exponent = _mm256_mul_ps(
        _mm256_cvtepi32_ps(exponent), _mm256_set1_ps(0.6931471805599453f));
    __m256 result = _mm256_add_ps(log_exponent, log_mantissa);

    if (valid_mask != 0xff) {
        float ratio_lanes[8];
        float result_lanes[8];
        _mm256_storeu_ps(ratio_lanes, ratio);
        _mm256_storeu_ps(result_lanes, result);
        for (int lane = 0; lane < 8; ++lane) {
            if ((valid_mask & (1 << lane)) == 0)
                result_lanes[lane] = logf(ratio_lanes[lane]);
        }
        result = _mm256_loadu_ps(result_lanes);
    }
    return result;
}

// AVX2 FMA form of Gm3's Horner evaluation; callers are runtime-dispatched
// only when both AVX2 and FMA are available.
static BS_TARGET_AVX2_FMA inline __m256 cnd_avx2(__m256 x) {
    const __m256 zero = _mm256_setzero_ps();
    const __m256 one = _mm256_set1_ps(1.f);
    const __m256 half = _mm256_set1_ps(.5f);
    const __m256 abs_mask = _mm256_castsi256_ps(_mm256_set1_epi32(0x7fffffff));
    const __m256 L = _mm256_and_ps(x, abs_mask);
    const __m256 k = _mm256_div_ps(
        one, _mm256_add_ps(one, _mm256_mul_ps(_mm256_set1_ps(.2316419f), L)));

    __m256 w = _mm256_fmadd_ps(_mm256_set1_ps(1.330274429f), k,
                               _mm256_set1_ps(-1.821255978f));
    w = _mm256_fmadd_ps(w, k, _mm256_set1_ps(1.781477937f));
    w = _mm256_fmadd_ps(w, k, _mm256_set1_ps(-0.356563782f));
    w = _mm256_fmadd_ps(w, k, _mm256_set1_ps(0.31938153f));
    w = _mm256_mul_ps(w, k);

    // Preserve the original exponent's multiply order.
    const __m256 negL = _mm256_sub_ps(zero, L);
    const __m256 exponent = _mm256_mul_ps(_mm256_mul_ps(negL, L), half);
    const __m256 exp_value = exp_avx2(exponent);
    const __m256 scale = _mm256_mul_ps(_mm256_set1_ps(0.39894228040f), exp_value);
    w = _mm256_mul_ps(w, scale);

    const __m256 positive = _mm256_cmp_ps(x, zero, _CMP_GT_OQ);
    return _mm256_blendv_ps(w, _mm256_sub_ps(one, w), positive);
}

static BS_TARGET_AVX2_FMA inline void black_scholes_avx2_block(
    float Sa[], float Xa[], float Ta[], float ra[], float va[],
    float result[], int i) {
    const __m256 S = _mm256_loadu_ps(Sa + i);
    const __m256 X = _mm256_loadu_ps(Xa + i);
    const __m256 T = _mm256_loadu_ps(Ta + i);
    const __m256 r = _mm256_loadu_ps(ra + i);
    const __m256 v = _mm256_loadu_ps(va + i);

    const __m256 ratio = _mm256_div_ps(S, X);
    const __m256 log_ratio = log_ratio_avx2(ratio);
    const __m256 sqrtT = _mm256_sqrt_ps(T);
    const __m256 vv_half = _mm256_mul_ps(
        _mm256_mul_ps(v, v), _mm256_set1_ps(.5f));
    const __m256 numerator = _mm256_add_ps(
        log_ratio, _mm256_mul_ps(_mm256_add_ps(r, vv_half), T));
    const __m256 v_sqrtT = _mm256_mul_ps(v, sqrtT);
    const __m256 d1 = _mm256_div_ps(numerator, v_sqrtT);
    const __m256 d2 = _mm256_sub_ps(d1, v_sqrtT);

    const __m256 neg_r = _mm256_sub_ps(_mm256_setzero_ps(), r);
    const __m256 discount_exponent = _mm256_mul_ps(neg_r, T);
    const __m256 discount = exp_avx2(discount_exponent);
    const __m256 cnd_d1 = cnd_avx2(d1);
    const __m256 cnd_d2 = cnd_avx2(d2);
    const __m256 value = _mm256_sub_ps(
        _mm256_mul_ps(S, cnd_d1),
        _mm256_mul_ps(_mm256_mul_ps(X, discount), cnd_d2));
    _mm256_storeu_ps(result + i, value);
}

static BS_TARGET_AVX2_FMA void black_scholes_avx2(
    float Sa[], float Xa[], float Ta[], float ra[], float va[],
    float result[], int count) {
    int i = 0;
    for (; i <= count - 8; i += 8)
        black_scholes_avx2_block(Sa, Xa, Ta, ra, va, result, i);
    for (; i < count; ++i)
        result[i] = black_scholes_value(Sa[i], Xa[i], Ta[i], ra[i], va[i]);
}

static inline int black_scholes_has_avx2_fma() {
    __builtin_cpu_init();
    return __builtin_cpu_supports("avx2") && __builtin_cpu_supports("fma");
}
#endif

void black_scholes_serial(float Sa[], float Xa[], float Ta[], float ra[], float va[], float result[], int count) {
#if BS_HAS_AVX2_DISPATCH
    if (black_scholes_has_avx2_fma()) {
        black_scholes_avx2(Sa, Xa, Ta, ra, va, result, count);
        return;
    }
#endif
    for (int i = 0; i < count; ++i)
        result[i] = black_scholes_value(Sa[i], Xa[i], Ta[i], ra[i], va[i]);
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

extern "C" void run(const void* input1, const void* input2, void* output,
                    int n, int parameter, int threads) {
    float* a = (float*)input1;
    float* result = (float*)output;

    if (threads <= 1) {
        black_scholes_serial(a, a + n, a + 2 * n, a + 3 * n,
                             a + 4 * n, result, n);
        return;
    }

#if BS_HAS_AVX2_DISPATCH
    if (black_scholes_has_avx2_fma()) {
        const int block_count = n / 8 + (n % 8 != 0);
        #pragma omp parallel for schedule(static) num_threads(threads)
        for (int block = 0; block < block_count; ++block) {
            const int i = block * 8;
            if (n - i >= 8) {
                black_scholes_avx2_block(a, a + n, a + 2 * n,
                                         a + 3 * n, a + 4 * n, result, i);
            } else {
                for (int j = i; j < n; ++j)
                    result[j] = black_scholes_value(a[j], a[n + j], a[2 * n + j],
                                                    a[3 * n + j], a[4 * n + j]);
            }
        }
        return;
    }
#endif

    #pragma omp parallel for simd schedule(static) num_threads(threads)
    for (int i = 0; i < n; ++i)
        result[i] = black_scholes_value(a[i], a[n + i], a[2 * n + i],
                                        a[3 * n + i], a[4 * n + i]);
}
