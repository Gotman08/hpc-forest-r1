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
#include <cfloat>
#include <cmath>
#include <math.h>
#include <omp.h>

#if defined(__SSE2__)
#include <emmintrin.h>
#endif

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

#if defined(__SSE2__)
static inline __m128 CND4(__m128 X, __m128 expTerm) {
    const __m128 one = _mm_set1_ps(1.f);
    const __m128 absMask = _mm_castsi128_ps(_mm_set1_epi32(0x7fffffff));
    const __m128 L = _mm_and_ps(X, absMask);

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
    w = _mm_mul_ps(w, _mm_mul_ps(_mm_set1_ps(0.39894228040f), expTerm));

    const __m128 positive = _mm_cmpgt_ps(X, _mm_setzero_ps());
    return _mm_or_ps(_mm_and_ps(positive, _mm_sub_ps(one, w)), _mm_andnot_ps(positive, w));
}
#endif

// Four-lane fallback and residual kernel used when AVX2 is unavailable or a four-item queue remains.
static inline void black_scholes_simd4(float Sa[], float Xa[], float Ta[], float ra[], float va[], float result[], int i) {
#if defined(__SSE2__)
    const __m128 S = _mm_loadu_ps(Sa + i);
    const __m128 X = _mm_loadu_ps(Xa + i);
    const __m128 T = _mm_loadu_ps(Ta + i);
    const __m128 r = _mm_loadu_ps(ra + i);
    const __m128 v = _mm_loadu_ps(va + i);

    float ratioLane[4], logLane[4];
    _mm_storeu_ps(ratioLane, _mm_div_ps(S, X));
#pragma omp simd
    for (int lane = 0; lane < 4; ++lane)
        logLane[lane] = logf(ratioLane[lane]);

    const __m128 sqrtT = _mm_sqrt_ps(T);
    const __m128 vSqrtT = _mm_mul_ps(v, sqrtT);
    const __m128 halfV2 = _mm_mul_ps(_mm_mul_ps(v, v), _mm_set1_ps(.5f));
    const __m128 drift = _mm_mul_ps(_mm_add_ps(r, halfV2), T);
    const __m128 d1 = _mm_div_ps(_mm_add_ps(_mm_loadu_ps(logLane), drift), vSqrtT);
    const __m128 d2 = _mm_sub_ps(d1, vSqrtT);

    const __m128 absMask = _mm_castsi128_ps(_mm_set1_epi32(0x7fffffff));
    float abs1Lane[4], abs2Lane[4], exp1Lane[4], exp2Lane[4];
    _mm_storeu_ps(abs1Lane, _mm_and_ps(d1, absMask));
    _mm_storeu_ps(abs2Lane, _mm_and_ps(d2, absMask));
#pragma omp simd
    for (int lane = 0; lane < 4; ++lane) {
        exp1Lane[lane] = expf(-abs1Lane[lane] * abs1Lane[lane] * .5f);
        exp2Lane[lane] = expf(-abs2Lane[lane] * abs2Lane[lane] * .5f);
    }

    const __m128 signMask = _mm_castsi128_ps(_mm_set1_epi32(static_cast<int>(0x80000000u)));
    float discountArgLane[4], discountLane[4];
    _mm_storeu_ps(discountArgLane, _mm_mul_ps(_mm_xor_ps(r, signMask), T));
#pragma omp simd
    for (int lane = 0; lane < 4; ++lane)
        discountLane[lane] = expf(discountArgLane[lane]);

    const __m128 cnd1 = CND4(d1, _mm_loadu_ps(exp1Lane));
    const __m128 cnd2 = CND4(d2, _mm_loadu_ps(exp2Lane));
    const __m128 price = _mm_sub_ps(_mm_mul_ps(S, cnd1),
                                    _mm_mul_ps(_mm_mul_ps(X, _mm_loadu_ps(discountLane)), cnd2));
    _mm_storeu_ps(result + i, price);
#else
    black_scholes_serial(Sa + i, Xa + i, Ta + i, ra + i, va + i, result + i, 4);
#endif
}

#if defined(__AVX2__)
static inline __m256 avx_abs8(__m256 x) {
    return _mm256_andnot_ps(_mm256_set1_ps(-0.0f), x);
}

static inline __m256 avx_finite_mask8(__m256 x) {
    return _mm256_cmp_ps(avx_abs8(x), _mm256_set1_ps(FLT_MAX), _CMP_LE_OQ);
}

static inline int avx_all8(__m256 mask) {
    return _mm256_movemask_ps(mask) == 0xff;
}

// Input must contain eight positive, finite normal values.
static inline __m256 avx_log8_normal(__m256 x) {
    const __m256 one = _mm256_set1_ps(1.0f);
    const __m256 half = _mm256_set1_ps(0.5f);
    const __m256 sqrt2 = _mm256_set1_ps(1.4142135623730951f);

    __m256i bits = _mm256_castps_si256(x);
    __m256i exponent = _mm256_sub_epi32(_mm256_srli_epi32(bits, 23), _mm256_set1_epi32(127));
    __m256 mantissa = _mm256_castsi256_ps(_mm256_or_si256(
        _mm256_and_si256(bits, _mm256_set1_epi32(0x007fffff)),
        _mm256_set1_epi32(0x3f800000)));

    __m256 above_sqrt2 = _mm256_cmp_ps(mantissa, sqrt2, _CMP_GT_OQ);
    mantissa = _mm256_blendv_ps(mantissa, _mm256_mul_ps(mantissa, half), above_sqrt2);
    exponent = _mm256_add_epi32(exponent, _mm256_and_si256(
        _mm256_castps_si256(above_sqrt2), _mm256_set1_epi32(1)));

    __m256 z = _mm256_div_ps(_mm256_sub_ps(mantissa, one), _mm256_add_ps(mantissa, one));
    __m256 z2 = _mm256_mul_ps(z, z);
    __m256 q = _mm256_set1_ps(1.0f / 13.0f);
    q = _mm256_add_ps(_mm256_set1_ps(1.0f / 11.0f), _mm256_mul_ps(z2, q));
    q = _mm256_add_ps(_mm256_set1_ps(1.0f / 9.0f), _mm256_mul_ps(z2, q));
    q = _mm256_add_ps(_mm256_set1_ps(1.0f / 7.0f), _mm256_mul_ps(z2, q));
    q = _mm256_add_ps(_mm256_set1_ps(1.0f / 5.0f), _mm256_mul_ps(z2, q));
    q = _mm256_add_ps(_mm256_set1_ps(1.0f / 3.0f), _mm256_mul_ps(z2, q));

    __m256 log_mantissa = _mm256_mul_ps(_mm256_set1_ps(2.0f),
        _mm256_mul_ps(z, _mm256_add_ps(one, _mm256_mul_ps(z2, q))));
    __m256 log_exponent = _mm256_mul_ps(_mm256_cvtepi32_ps(exponent),
        _mm256_set1_ps(0.6931471805599453f));
    return _mm256_add_ps(log_mantissa, log_exponent);
}

// Range-reduced SIMD exponential with scalar libm handling for out-of-range lanes.
static inline __m256 avx_exp8(__m256 x) {
    const __m256 zero = _mm256_setzero_ps();
    const __m256 one = _mm256_set1_ps(1.0f);
    __m256 valid = _mm256_and_ps(
        _mm256_cmp_ps(x, _mm256_set1_ps(-80.0f), _CMP_GE_OQ),
        _mm256_cmp_ps(x, _mm256_set1_ps(80.0f), _CMP_LE_OQ));
    int valid_bits = _mm256_movemask_ps(valid);
    __m256 safe_x = _mm256_blendv_ps(zero, x, valid);

    __m256 n_float = _mm256_floor_ps(_mm256_mul_ps(
        safe_x, _mm256_set1_ps(1.4426950408889634f)));
    __m256 r = _mm256_sub_ps(safe_x, _mm256_mul_ps(n_float,
        _mm256_set1_ps(0.693145751953125f)));
    r = _mm256_sub_ps(r, _mm256_mul_ps(n_float,
        _mm256_set1_ps(1.428606765330187045e-6f)));

    __m256 p = _mm256_set1_ps(1.0f / 40320.0f);
    p = _mm256_add_ps(_mm256_set1_ps(1.0f / 5040.0f), _mm256_mul_ps(r, p));
    p = _mm256_add_ps(_mm256_set1_ps(1.0f / 720.0f), _mm256_mul_ps(r, p));
    p = _mm256_add_ps(_mm256_set1_ps(1.0f / 120.0f), _mm256_mul_ps(r, p));
    p = _mm256_add_ps(_mm256_set1_ps(1.0f / 24.0f), _mm256_mul_ps(r, p));
    p = _mm256_add_ps(_mm256_set1_ps(1.0f / 6.0f), _mm256_mul_ps(r, p));
    p = _mm256_add_ps(_mm256_set1_ps(0.5f), _mm256_mul_ps(r, p));
    __m256 exp_r = _mm256_add_ps(_mm256_add_ps(one, r),
        _mm256_mul_ps(_mm256_mul_ps(r, r), p));

    __m256i n = _mm256_cvttps_epi32(n_float);
    __m256i scale_bits = _mm256_slli_epi32(
        _mm256_add_epi32(n, _mm256_set1_epi32(127)), 23);
    __m256 result = _mm256_mul_ps(exp_r, _mm256_castsi256_ps(scale_bits));

    if (valid_bits != 0xff) {
        alignas(32) float lanes[8];
        alignas(32) float values[8];
        _mm256_store_ps(lanes, x);
        _mm256_store_ps(values, result);
        for (int lane = 0; lane < 8; ++lane) {
            if ((valid_bits & (1 << lane)) == 0)
                values[lane] = expf(lanes[lane]);
        }
        result = _mm256_load_ps(values);
    }
    return result;
}

static inline __m256 avx_cnd8(__m256 x) {
    const __m256 one = _mm256_set1_ps(1.0f);
    __m256 l = avx_abs8(x);
    __m256 k = _mm256_div_ps(one, _mm256_add_ps(one,
        _mm256_mul_ps(_mm256_set1_ps(0.2316419f), l)));
    __m256 k2 = _mm256_mul_ps(k, k);
    __m256 k3 = _mm256_mul_ps(k2, k);
    __m256 k4 = _mm256_mul_ps(k2, k2);
    __m256 k5 = _mm256_mul_ps(k3, k2);

    __m256 w = _mm256_sub_ps(_mm256_mul_ps(_mm256_set1_ps(0.31938153f), k),
        _mm256_mul_ps(_mm256_set1_ps(0.356563782f), k2));
    w = _mm256_add_ps(w, _mm256_mul_ps(_mm256_set1_ps(1.781477937f), k3));
    w = _mm256_add_ps(w, _mm256_mul_ps(_mm256_set1_ps(-1.821255978f), k4));
    w = _mm256_add_ps(w, _mm256_mul_ps(_mm256_set1_ps(1.330274429f), k5));

    __m256 exponent = _mm256_mul_ps(
        _mm256_mul_ps(_mm256_sub_ps(_mm256_setzero_ps(), l), l),
        _mm256_set1_ps(0.5f));
    w = _mm256_mul_ps(w, _mm256_mul_ps(_mm256_set1_ps(0.39894228040f),
        avx_exp8(exponent)));
    __m256 positive = _mm256_cmp_ps(x, _mm256_setzero_ps(), _CMP_GT_OQ);
    return _mm256_blendv_ps(w, _mm256_sub_ps(one, w), positive);
}

// Processes a single slice only; the outer dispatcher controls all thread scheduling.
static void black_scholes_avx2(float Sa[], float Xa[], float Ta[], float ra[],
                               float va[], float result[], int count) {
    const __m256 min_normal = _mm256_set1_ps(FLT_MIN);
    const __m256 zero = _mm256_setzero_ps();
    int i = 0;

    for (; count - i >= 8; i += 8) {
        __m256 s = _mm256_loadu_ps(Sa + i);
        __m256 x = _mm256_loadu_ps(Xa + i);
        __m256 t = _mm256_loadu_ps(Ta + i);
        __m256 r = _mm256_loadu_ps(ra + i);
        __m256 v = _mm256_loadu_ps(va + i);

        __m256 safe = _mm256_and_ps(_mm256_cmp_ps(s, min_normal, _CMP_GE_OQ),
                                    avx_finite_mask8(s));
        safe = _mm256_and_ps(safe, _mm256_and_ps(
            _mm256_cmp_ps(x, min_normal, _CMP_GE_OQ), avx_finite_mask8(x)));
        safe = _mm256_and_ps(safe, _mm256_and_ps(
            _mm256_cmp_ps(t, min_normal, _CMP_GE_OQ), avx_finite_mask8(t)));
        safe = _mm256_and_ps(safe, _mm256_and_ps(
            _mm256_cmp_ps(v, min_normal, _CMP_GE_OQ), avx_finite_mask8(v)));
        __m256 r_is_zero = _mm256_cmp_ps(r, zero, _CMP_EQ_OQ);
        __m256 r_is_normal = _mm256_cmp_ps(avx_abs8(r), min_normal, _CMP_GE_OQ);
        safe = _mm256_and_ps(safe, _mm256_and_ps(avx_finite_mask8(r),
            _mm256_or_ps(r_is_zero, r_is_normal)));

        __m256 ratio = _mm256_div_ps(s, x);
        safe = _mm256_and_ps(safe, _mm256_and_ps(
            _mm256_cmp_ps(ratio, min_normal, _CMP_GE_OQ), avx_finite_mask8(ratio)));
        if (!avx_all8(safe)) {
            black_scholes_serial(Sa + i, Xa + i, Ta + i, ra + i, va + i,
                                 result + i, 8);
            continue;
        }

        __m256 sqrt_t = _mm256_sqrt_ps(t);
        __m256 denominator = _mm256_mul_ps(v, sqrt_t);
        safe = _mm256_and_ps(_mm256_cmp_ps(denominator, min_normal, _CMP_GE_OQ),
                             avx_finite_mask8(denominator));
        if (!avx_all8(safe)) {
            black_scholes_serial(Sa + i, Xa + i, Ta + i, ra + i, va + i,
                                 result + i, 8);
            continue;
        }

        __m256 log_ratio = avx_log8_normal(ratio);
        __m256 variance = _mm256_mul_ps(_mm256_mul_ps(v, v), _mm256_set1_ps(0.5f));
        __m256 growth = _mm256_mul_ps(_mm256_add_ps(r, variance), t);
        __m256 d1 = _mm256_div_ps(_mm256_add_ps(log_ratio, growth), denominator);
        __m256 d2 = _mm256_sub_ps(d1, denominator);
        safe = _mm256_and_ps(avx_finite_mask8(d1), avx_finite_mask8(d2));
        if (!avx_all8(safe)) {
            black_scholes_serial(Sa + i, Xa + i, Ta + i, ra + i, va + i,
                                 result + i, 8);
            continue;
        }

        __m256 discount = avx_exp8(_mm256_sub_ps(zero, _mm256_mul_ps(r, t)));
        __m256 value = _mm256_sub_ps(
            _mm256_mul_ps(s, avx_cnd8(d1)),
            _mm256_mul_ps(_mm256_mul_ps(x, discount), avx_cnd8(d2)));
        _mm256_storeu_ps(result + i, value);
    }

    if (i < count)
        black_scholes_serial(Sa + i, Xa + i, Ta + i, ra + i, va + i,
                             result + i, count - i);
}
#endif

void black_scholes_parallel(float Sa[], float Xa[], float Ta[], float ra[], float va[],
                            float result[], int count, int threads) {
    const int vector_count = count - count % 4;
    const int blocks = vector_count / 4;
    const int team_size = std::min(threads, blocks);

    // Preserve the small-work cutoff and avoid an OpenMP team for short calls.
    if (threads <= 1 || blocks == 0 || blocks / team_size < 4) {
#if defined(__AVX2__)
        const int avx_count = vector_count - vector_count % 8;
        if (avx_count > 0)
            black_scholes_avx2(Sa, Xa, Ta, ra, va, result, avx_count);
        if (avx_count < vector_count)
            black_scholes_simd4(Sa, Xa, Ta, ra, va, result, avx_count);
#else
        for (int block = 0; block < blocks; ++block)
            black_scholes_simd4(Sa, Xa, Ta, ra, va, result, block * 4);
#endif
        if (vector_count < count) {
            black_scholes_serial(Sa + vector_count, Xa + vector_count, Ta + vector_count,
                                 ra + vector_count, va + vector_count, result + vector_count,
                                 count - vector_count);
        }
        return;
    }

#if defined(__AVX2__)
    const int avx_blocks = vector_count / 8;
#pragma omp parallel num_threads(team_size)
    {
        const int tid = omp_get_thread_num();
        const int actual_team = omp_get_num_threads();
        const int blocks_per_thread = avx_blocks / actual_team;
        const int extra_blocks = avx_blocks % actual_team;
        const int first_block = tid * blocks_per_thread + std::min(tid, extra_blocks);
        const int owned_blocks = blocks_per_thread + (tid < extra_blocks ? 1 : 0);
        if (owned_blocks > 0) {
            const int first = first_block * 8;
            black_scholes_avx2(Sa + first, Xa + first, Ta + first, ra + first,
                               va + first, result + first, owned_blocks * 8);
        }
    }
    const int avx_count = avx_blocks * 8;
    if (avx_count < vector_count)
        black_scholes_simd4(Sa, Xa, Ta, ra, va, result, avx_count);
#else
#pragma omp parallel for schedule(static) num_threads(team_size)
    for (int block = 0; block < blocks; ++block)
        black_scholes_simd4(Sa, Xa, Ta, ra, va, result, block * 4);
#endif

    if (vector_count < count) {
        black_scholes_serial(Sa + vector_count, Xa + vector_count, Ta + vector_count,
                             ra + vector_count, va + vector_count, result + vector_count,
                             count - vector_count);
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
    black_scholes_parallel(a, a + n, a + 2 * n, a + 3 * n, a + 4 * n,
                           (float*)output, n, threads);
}
