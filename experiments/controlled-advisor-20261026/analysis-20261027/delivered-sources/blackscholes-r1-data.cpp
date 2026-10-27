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

    const float invSqrt2Pi = 0.39894228040f;
    float odd = k * (0.31938153f + k2 * (1.781477937f + 1.330274429f * k2));
    float even = k2 * (-0.356563782f - 1.821255978f * k2);
    float w = odd + even;
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
// Approximate exp for lanes in [-10, 0]; use expf for every other lane.
// Range reduction keeps the degree-eight Taylor evaluation well-conditioned.
static inline __m256 exp_approx8(__m256 x) {
    const __m256 zero = _mm256_setzero_ps();
    const __m256 one = _mm256_set1_ps(1.0f);
    const __m256 lower = _mm256_set1_ps(-10.0f);
    const __m256 valid = _mm256_and_ps(
        _mm256_cmp_ps(x, lower, _CMP_GE_OQ),
        _mm256_cmp_ps(x, zero, _CMP_LE_OQ));
    const __m256 safe_x = _mm256_blendv_ps(zero, x, valid);

    const __m256 log2e = _mm256_set1_ps(1.4426950408889634f);
    const __m256 ln2 = _mm256_set1_ps(0.6931471805599453f);
    const __m256 y = _mm256_mul_ps(safe_x, log2e);
    const __m256 n = _mm256_round_ps(
        y, _MM_FROUND_TO_NEAREST_INT | _MM_FROUND_NO_EXC);
    const __m256 z = _mm256_sub_ps(safe_x, _mm256_mul_ps(n, ln2));

    __m256 polynomial = _mm256_set1_ps(1.0f / 40320.0f);
    polynomial = _mm256_add_ps(
        _mm256_mul_ps(polynomial, z), _mm256_set1_ps(1.0f / 5040.0f));
    polynomial = _mm256_add_ps(
        _mm256_mul_ps(polynomial, z), _mm256_set1_ps(1.0f / 720.0f));
    polynomial = _mm256_add_ps(
        _mm256_mul_ps(polynomial, z), _mm256_set1_ps(1.0f / 120.0f));
    polynomial = _mm256_add_ps(
        _mm256_mul_ps(polynomial, z), _mm256_set1_ps(1.0f / 24.0f));
    polynomial = _mm256_add_ps(
        _mm256_mul_ps(polynomial, z), _mm256_set1_ps(1.0f / 6.0f));
    polynomial = _mm256_add_ps(
        _mm256_mul_ps(polynomial, z), _mm256_set1_ps(0.5f));
    polynomial = _mm256_add_ps(
        _mm256_mul_ps(polynomial, z), one);
    polynomial = _mm256_add_ps(
        _mm256_mul_ps(polynomial, z), one);

    const __m256i exponent = _mm256_cvttps_epi32(n);
    const __m256i exponent_bits = _mm256_slli_epi32(
        _mm256_add_epi32(exponent, _mm256_set1_epi32(127)), 23);
    __m256 values = _mm256_mul_ps(_mm256_castsi256_ps(exponent_bits), polynomial);

    const int fallback_lanes = (~_mm256_movemask_ps(valid)) & 0xff;
    if (fallback_lanes != 0) {
        alignas(32) float arguments[8];
        alignas(32) float lanes[8];
        _mm256_store_ps(arguments, x);
        _mm256_store_ps(lanes, values);
        for (int lane = 0; lane < 8; ++lane) {
            if (fallback_lanes & (1 << lane))
                lanes[lane] = expf(arguments[lane]);
        }
        values = _mm256_load_ps(lanes);
    }
    return values;
}

// Use the bounded degree-nine Taylor approximation for exp on [-0.5, 0.5].
// Unsupported lanes retain the libm result.
static inline __m256 exp_t4_bounded8(__m256 x) {
    const __m256 zero = _mm256_setzero_ps();
    const __m256 in_range = _mm256_and_ps(
        _mm256_cmp_ps(x, _mm256_set1_ps(-0.5f), _CMP_GE_OQ),
        _mm256_cmp_ps(x, _mm256_set1_ps(0.5f), _CMP_LE_OQ));
    const __m256 safe_x = _mm256_blendv_ps(zero, x, in_range);

    __m256 p = _mm256_set1_ps(1.f / 362880.f);
    p = _mm256_add_ps(_mm256_mul_ps(p, safe_x), _mm256_set1_ps(1.f / 40320.f));
    p = _mm256_add_ps(_mm256_mul_ps(p, safe_x), _mm256_set1_ps(1.f / 5040.f));
    p = _mm256_add_ps(_mm256_mul_ps(p, safe_x), _mm256_set1_ps(1.f / 720.f));
    p = _mm256_add_ps(_mm256_mul_ps(p, safe_x), _mm256_set1_ps(1.f / 120.f));
    p = _mm256_add_ps(_mm256_mul_ps(p, safe_x), _mm256_set1_ps(1.f / 24.f));
    p = _mm256_add_ps(_mm256_mul_ps(p, safe_x), _mm256_set1_ps(1.f / 6.f));
    p = _mm256_add_ps(_mm256_mul_ps(p, safe_x), _mm256_set1_ps(0.5f));
    p = _mm256_add_ps(_mm256_mul_ps(p, safe_x), _mm256_set1_ps(1.f));
    p = _mm256_add_ps(_mm256_mul_ps(p, safe_x), _mm256_set1_ps(1.f));

    const int fallback_lanes = (~_mm256_movemask_ps(in_range)) & 0xff;
    if (fallback_lanes != 0) {
        alignas(32) float arguments[8];
        alignas(32) float lanes[8];
        _mm256_store_ps(arguments, x);
        _mm256_store_ps(lanes, p);
        for (int lane = 0; lane < 8; ++lane) {
            if (fallback_lanes & (1 << lane))
                lanes[lane] = expf(arguments[lane]);
        }
        p = _mm256_load_ps(lanes);
    }
    return p;
}

// Approximate log for positive normal ratios using a normalized mantissa and
// an atanh series. Other lanes use the exact scalar logf fallback.
static inline __m256 log8_t2(__m256 ratio) {
    const __m256 one = _mm256_set1_ps(1.f);
    const __m256i zero_i = _mm256_setzero_si256();
    const __m256i bits = _mm256_castps_si256(ratio);
    const __m256i exp_bits = _mm256_and_si256(
        bits, _mm256_set1_epi32(0x7f800000));
    const __m256i positive = _mm256_cmpgt_epi32(bits, zero_i);
    const __m256i normal_exp = _mm256_and_si256(
        _mm256_cmpgt_epi32(exp_bits, zero_i),
        _mm256_cmpgt_epi32(_mm256_set1_epi32(0x7f800000), exp_bits));
    const __m256 valid = _mm256_castsi256_ps(
        _mm256_and_si256(positive, normal_exp));
    const __m256 safe_ratio = _mm256_blendv_ps(one, ratio, valid);
    const __m256i safe_bits = _mm256_castps_si256(safe_ratio);

    __m256i exponent = _mm256_sub_epi32(
        _mm256_and_si256(_mm256_srli_epi32(safe_bits, 23),
                         _mm256_set1_epi32(0xff)),
        _mm256_set1_epi32(127));
    const __m256i mantissa_bits = _mm256_or_si256(
        _mm256_and_si256(safe_bits, _mm256_set1_epi32(0x007fffff)),
        _mm256_set1_epi32(0x3f800000));
    __m256 mantissa = _mm256_castsi256_ps(mantissa_bits);

    // Keep the mantissa near one, limiting |(m-1)/(m+1)| for the series.
    const __m256 recenter = _mm256_cmp_ps(
        mantissa, _mm256_set1_ps(1.41421356237f), _CMP_GT_OQ);
    mantissa = _mm256_blendv_ps(
        mantissa, _mm256_mul_ps(mantissa, _mm256_set1_ps(0.5f)), recenter);
    exponent = _mm256_add_epi32(
        exponent,
        _mm256_and_si256(_mm256_castps_si256(recenter), _mm256_set1_epi32(1)));

    const __m256 y = _mm256_div_ps(
        _mm256_sub_ps(mantissa, one), _mm256_add_ps(mantissa, one));
    const __m256 y2 = _mm256_mul_ps(y, y);
    __m256 p = _mm256_set1_ps(1.f / 9.f);
    p = _mm256_add_ps(_mm256_mul_ps(p, y2), _mm256_set1_ps(1.f / 7.f));
    p = _mm256_add_ps(_mm256_mul_ps(p, y2), _mm256_set1_ps(1.f / 5.f));
    p = _mm256_add_ps(_mm256_mul_ps(p, y2), _mm256_set1_ps(1.f / 3.f));
    p = _mm256_add_ps(_mm256_mul_ps(p, y2), one);
    const __m256 log_mantissa = _mm256_mul_ps(
        _mm256_mul_ps(_mm256_set1_ps(2.f), y), p);

    const __m256 exponent_f = _mm256_cvtepi32_ps(exponent);
    const __m256 exponent_hi = _mm256_mul_ps(
        exponent_f, _mm256_set1_ps(0.693145751953125f));
    const __m256 exponent_lo_and_mantissa = _mm256_add_ps(
        _mm256_mul_ps(exponent_f, _mm256_set1_ps(1.428606765330187e-6f)),
        log_mantissa);
    __m256 values = _mm256_add_ps(exponent_hi, exponent_lo_and_mantissa);

    const int fallback_lanes = (~_mm256_movemask_ps(valid)) & 0xff;
    if (fallback_lanes != 0) {
        alignas(32) float arguments[8];
        alignas(32) float lanes[8];
        _mm256_store_ps(arguments, ratio);
        _mm256_store_ps(lanes, values);
        for (int lane = 0; lane < 8; ++lane) {
            if (fallback_lanes & (1 << lane))
                lanes[lane] = logf(arguments[lane]);
        }
        values = _mm256_load_ps(lanes);
    }
    return values;
}

// Evaluate eight independent lanes using paired odd/even CND coefficients.
static inline __m256 CND8(__m256 X) {
    const __m256 zero = _mm256_setzero_ps();
    const __m256 one = _mm256_set1_ps(1.f);
    const __m256 half = _mm256_set1_ps(.5f);
    const __m256 sign_mask = _mm256_set1_ps(-0.0f);
    const __m256 abs_mask = _mm256_castsi256_ps(_mm256_set1_epi32(0x7fffffff));
    const __m256 L = _mm256_and_ps(X, abs_mask);

    const __m256 k = _mm256_div_ps(
        one,
        _mm256_add_ps(one, _mm256_mul_ps(_mm256_set1_ps(.2316419f), L)));
    const __m256 k2 = _mm256_mul_ps(k, k);

    const __m256 odd_inner = _mm256_add_ps(
        _mm256_set1_ps(1.781477937f),
        _mm256_mul_ps(_mm256_set1_ps(1.330274429f), k2));
    const __m256 odd = _mm256_mul_ps(
        k,
        _mm256_add_ps(
            _mm256_set1_ps(.31938153f),
            _mm256_mul_ps(k2, odd_inner)));
    const __m256 even_inner = _mm256_add_ps(
        _mm256_set1_ps(-.356563782f),
        _mm256_mul_ps(_mm256_set1_ps(-1.821255978f), k2));
    const __m256 even = _mm256_mul_ps(k2, even_inner);
    const __m256 poly = _mm256_add_ps(odd, even);

    const __m256 neg_L = _mm256_xor_ps(L, sign_mask);
    const __m256 exponent = _mm256_mul_ps(
        _mm256_mul_ps(neg_L, L), half);
    const __m256 exp_values = exp_approx8(exponent);

    __m256 w = _mm256_mul_ps(
        poly,
        _mm256_mul_ps(_mm256_set1_ps(0.39894228040f), exp_values));
    const __m256 positive_w = _mm256_sub_ps(one, w);
    const __m256 positive_mask = _mm256_cmp_ps(X, zero, _CMP_GT_OQ);
    return _mm256_blendv_ps(w, positive_w, positive_mask);
}

// Process one full AVX2 vector; callers retain responsibility for any tail.
static inline void black_scholes_avx2_block(float Sa[], float Xa[], float Ta[], float ra[], float va[], float result[], int i) {
    const __m256 half = _mm256_set1_ps(.5f);
    const __m256 sign_mask = _mm256_set1_ps(-0.0f);

    const __m256 S = _mm256_loadu_ps(Sa + i);
    const __m256 X = _mm256_loadu_ps(Xa + i);
    const __m256 T = _mm256_loadu_ps(Ta + i);
    const __m256 r = _mm256_loadu_ps(ra + i);
    const __m256 v = _mm256_loadu_ps(va + i);

    const __m256 ratio = _mm256_div_ps(S, X);
    const __m256 log_values = log8_t2(ratio);

    const __m256 sqrt_T = _mm256_sqrt_ps(T);
    const __m256 v2_half = _mm256_mul_ps(_mm256_mul_ps(v, v), half);
    const __m256 drift = _mm256_mul_ps(_mm256_add_ps(r, v2_half), T);
    const __m256 v_sqrt_T = _mm256_mul_ps(v, sqrt_T);
    const __m256 d1 = _mm256_div_ps(_mm256_add_ps(log_values, drift), v_sqrt_T);
    const __m256 d2 = _mm256_sub_ps(d1, v_sqrt_T);

    const __m256 rt = _mm256_mul_ps(r, T);
    const __m256 neg_rt = _mm256_xor_ps(rt, sign_mask);
    const __m256 discount = exp_t4_bounded8(neg_rt);

    const __m256 cnd1 = CND8(d1);
    const __m256 cnd2 = CND8(d2);
    const __m256 call_value = _mm256_mul_ps(S, cnd1);
    const __m256 put_value = _mm256_mul_ps(
        _mm256_mul_ps(X, discount), cnd2);
    _mm256_storeu_ps(result + i, _mm256_sub_ps(call_value, put_value));
}

static void black_scholes_avx2(float Sa[], float Xa[], float Ta[], float ra[], float va[], float result[], int count) {
    int i = 0;
    for (; count - i >= 8; i += 8)
        black_scholes_avx2_block(Sa, Xa, Ta, ra, va, result, i);

    if (i < count)
        black_scholes_serial(Sa + i, Xa + i, Ta + i, ra + i, va + i, result + i, count - i);
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
    float* a = (float*)input1;
    float* result = (float*)output;

#if defined(__AVX2__)
    // Avoid team overhead unless there is enough vector work to distribute.
    if (threads <= 1 || n < 256) {
        black_scholes_avx2(a, a + n, a + 2 * n, a + 3 * n, a + 4 * n, result, n);
        return;
    }

    const int vector_count = n / 8;
    const int team_size = threads < vector_count ? threads : vector_count;
    #pragma omp parallel for schedule(static) num_threads(team_size)
    for (int block = 0; block < vector_count; ++block) {
        black_scholes_avx2_block(a, a + n, a + 2 * n, a + 3 * n, a + 4 * n, result, block * 8);
    }

    const int vector_end = vector_count * 8;
    if (vector_end < n)
        black_scholes_serial(a + vector_end, a + n + vector_end, a + 2 * n + vector_end,
                             a + 3 * n + vector_end, a + 4 * n + vector_end,
                             result + vector_end, n - vector_end);
#else
    if (threads <= 1 || n < 256) {
        black_scholes_serial(a, a + n, a + 2 * n, a + 3 * n, a + 4 * n, result, n);
        return;
    }

    const int team_size = threads < n ? threads : n;
    #pragma omp parallel for schedule(static) num_threads(team_size)
    for (int i = 0; i < n; ++i) {
        float S = a[i], X = a[n + i];
        float T = a[2 * n + i], r = a[3 * n + i];
        float v = a[4 * n + i];

        float d1 = (logf(S / X) + (r + v * v * .5f) * T) / (v * sqrtf(T));
        float d2 = d1 - v * sqrtf(T);

        result[i] = S * CND(d1) - X * expf(-r * T) * CND(d2);
    }
#endif
}
