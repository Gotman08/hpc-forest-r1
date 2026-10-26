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
#include <cmath>
#include <cfloat>
#include <cstring>
#include <cstdint>
#include <omp.h>

#if defined(__AVX2__)
#include <immintrin.h>

static inline __m256 avx_log_approx(__m256 x) {
    const __m256 min_normal = _mm256_set1_ps(1.1754943508222875e-38f);
    const __m256 subnormal = _mm256_cmp_ps(x, min_normal, _CMP_LT_OQ);
    const __m256 scaled = _mm256_mul_ps(x, _mm256_set1_ps(8388608.0f));
    const __m256 normalized = _mm256_blendv_ps(x, scaled, subnormal);

    const __m256i bits = _mm256_castps_si256(normalized);
    const __m256i exp_bits = _mm256_and_si256(_mm256_srli_epi32(bits, 23), _mm256_set1_epi32(255));
    __m256i exponent = _mm256_sub_epi32(exp_bits, _mm256_set1_epi32(127));
    exponent = _mm256_sub_epi32(
        exponent,
        _mm256_and_si256(_mm256_castps_si256(subnormal), _mm256_set1_epi32(23)));

    const __m256i mantissa_bits = _mm256_or_si256(
        _mm256_and_si256(bits, _mm256_set1_epi32(0x007fffff)),
        _mm256_set1_epi32(0x3f800000));
    __m256 mantissa = _mm256_castsi256_ps(mantissa_bits);
    const __m256 adjust = _mm256_cmp_ps(mantissa, _mm256_set1_ps(1.4142135623730951f), _CMP_GE_OQ);
    mantissa = _mm256_blendv_ps(mantissa, _mm256_mul_ps(mantissa, _mm256_set1_ps(0.5f)), adjust);
    exponent = _mm256_add_epi32(
        exponent,
        _mm256_and_si256(_mm256_castps_si256(adjust), _mm256_set1_epi32(1)));

    const __m256 z = _mm256_div_ps(
        _mm256_sub_ps(mantissa, _mm256_set1_ps(1.0f)),
        _mm256_add_ps(mantissa, _mm256_set1_ps(1.0f)));
    const __m256 z2 = _mm256_mul_ps(z, z);

    __m256 polynomial = _mm256_set1_ps(1.0f / 9.0f);
    polynomial = _mm256_add_ps(_mm256_set1_ps(1.0f / 7.0f), _mm256_mul_ps(z2, polynomial));
    polynomial = _mm256_add_ps(_mm256_set1_ps(1.0f / 5.0f), _mm256_mul_ps(z2, polynomial));
    polynomial = _mm256_add_ps(_mm256_set1_ps(1.0f / 3.0f), _mm256_mul_ps(z2, polynomial));
    polynomial = _mm256_add_ps(_mm256_set1_ps(1.0f), _mm256_mul_ps(z2, polynomial));

    const __m256 log_mantissa = _mm256_mul_ps(_mm256_mul_ps(_mm256_set1_ps(2.0f), z), polynomial);
    const __m256 log_exponent = _mm256_mul_ps(
        _mm256_cvtepi32_ps(exponent), _mm256_set1_ps(0.6931471805599453f));
    return _mm256_add_ps(log_exponent, log_mantissa);
}

static inline __m256 avx_log8(__m256 x) {
    const __m256 positive = _mm256_cmp_ps(x, _mm256_set1_ps(1.1754943508222875e-38f), _CMP_GE_OQ);
    const __m256 finite = _mm256_cmp_ps(x, _mm256_set1_ps(FLT_MAX), _CMP_LE_OQ);
    const __m256 valid = _mm256_and_ps(positive, finite);
    const __m256 safe_x = _mm256_blendv_ps(_mm256_set1_ps(1.0f), x, valid);
    const __m256 approx = avx_log_approx(safe_x);

    float input[8];
    float result[8];
    int valid_lanes[8];
    _mm256_storeu_ps(input, x);
    _mm256_storeu_ps(result, approx);
    _mm256_storeu_si256(reinterpret_cast<__m256i*>(valid_lanes), _mm256_castps_si256(valid));
    for (int lane = 0; lane < 8; ++lane) {
        if (valid_lanes[lane] == 0)
            result[lane] = logf(input[lane]);
    }
    return _mm256_loadu_ps(result);
}

static inline __m256 avx_exp_approx(__m256 x) {
    const __m256 log2e = _mm256_set1_ps(1.4426950408889634f);
    const __m256 nf = _mm256_mul_ps(x, log2e);
    const __m256i n = _mm256_cvtps_epi32(nf);
    const __m256 n_float = _mm256_cvtepi32_ps(n);

    const __m256 r_hi = _mm256_sub_ps(
        x, _mm256_mul_ps(n_float, _mm256_set1_ps(0.693359375f)));
    const __m256 r = _mm256_sub_ps(
        r_hi, _mm256_mul_ps(n_float, _mm256_set1_ps(-0.00021219444005469058f)));

    __m256 p = _mm256_set1_ps(1.0f / 5040.0f);
    p = _mm256_add_ps(_mm256_set1_ps(1.0f / 720.0f), _mm256_mul_ps(r, p));
    p = _mm256_add_ps(_mm256_set1_ps(1.0f / 120.0f), _mm256_mul_ps(r, p));
    p = _mm256_add_ps(_mm256_set1_ps(1.0f / 24.0f), _mm256_mul_ps(r, p));
    p = _mm256_add_ps(_mm256_set1_ps(1.0f / 6.0f), _mm256_mul_ps(r, p));
    p = _mm256_add_ps(_mm256_set1_ps(0.5f), _mm256_mul_ps(r, p));
    p = _mm256_add_ps(_mm256_set1_ps(1.0f), _mm256_mul_ps(r, p));
    p = _mm256_add_ps(_mm256_set1_ps(1.0f), _mm256_mul_ps(r, p));

    const __m256i exp_bits = _mm256_slli_epi32(
        _mm256_add_epi32(n, _mm256_set1_epi32(127)), 23);
    const __m256 scale = _mm256_castsi256_ps(exp_bits);
    return _mm256_mul_ps(scale, p);
}

static inline __m256 avx_exp8(__m256 x) {
    const __m256 in_range = _mm256_and_ps(
        _mm256_cmp_ps(x, _mm256_set1_ps(-80.0f), _CMP_GE_OQ),
        _mm256_cmp_ps(x, _mm256_set1_ps(80.0f), _CMP_LE_OQ));
    const __m256 safe_x = _mm256_blendv_ps(_mm256_setzero_ps(), x, in_range);
    const __m256 approx = avx_exp_approx(safe_x);

    float input[8];
    float result[8];
    int valid_lanes[8];
    _mm256_storeu_ps(input, x);
    _mm256_storeu_ps(result, approx);
    _mm256_storeu_si256(reinterpret_cast<__m256i*>(valid_lanes), _mm256_castps_si256(in_range));
    for (int lane = 0; lane < 8; ++lane) {
        if (valid_lanes[lane] == 0)
            result[lane] = expf(input[lane]);
    }
    return _mm256_loadu_ps(result);
}

static inline __m256 avx_cnd8(__m256 x) {
    const __m256 zero = _mm256_setzero_ps();
    const __m256 one = _mm256_set1_ps(1.0f);
    const __m256 l = _mm256_and_ps(
        x, _mm256_castsi256_ps(_mm256_set1_epi32(0x7fffffff)));

    const __m256 k = _mm256_div_ps(
        one,
        _mm256_add_ps(one, _mm256_mul_ps(_mm256_set1_ps(0.2316419f), l)));

    // Horner evaluation of the same five-coefficient CND polynomial.
    __m256 w = _mm256_add_ps(
        _mm256_mul_ps(_mm256_set1_ps(1.330274429f), k),
        _mm256_set1_ps(-1.821255978f));
    w = _mm256_add_ps(_mm256_mul_ps(w, k), _mm256_set1_ps(1.781477937f));
    w = _mm256_sub_ps(_mm256_mul_ps(w, k), _mm256_set1_ps(0.356563782f));
    w = _mm256_add_ps(_mm256_mul_ps(w, k), _mm256_set1_ps(0.31938153f));
    w = _mm256_mul_ps(w, k);

    const __m256 negative_l = _mm256_sub_ps(zero, l);
    __m256 exp_arg = _mm256_mul_ps(negative_l, l);
    exp_arg = _mm256_mul_ps(exp_arg, _mm256_set1_ps(0.5f));
    const __m256 scale = _mm256_mul_ps(
        _mm256_set1_ps(0.39894228040f), avx_exp8(exp_arg));
    w = _mm256_mul_ps(w, scale);

    const __m256 positive = _mm256_cmp_ps(x, zero, _CMP_GT_OQ);
    return _mm256_blendv_ps(w, _mm256_sub_ps(one, w), positive);
}

static inline void black_scholes_avx2_block(
    float Sa[], float Xa[], float Ta[], float ra[], float va[], float result[], int block) {
    const int i = block * 8;
    const __m256 S = _mm256_loadu_ps(Sa + i);
    const __m256 X = _mm256_loadu_ps(Xa + i);
    const __m256 T = _mm256_loadu_ps(Ta + i);
    const __m256 r = _mm256_loadu_ps(ra + i);
    const __m256 v = _mm256_loadu_ps(va + i);

    const __m256 half = _mm256_set1_ps(0.5f);
    const __m256 zero = _mm256_setzero_ps();
    const __m256 ratio = _mm256_div_ps(S, X);
    const __m256 log_ratio = avx_log8(ratio);
    const __m256 v_squared = _mm256_mul_ps(v, v);
    const __m256 drift = _mm256_add_ps(r, _mm256_mul_ps(v_squared, half));
    const __m256 numerator = _mm256_add_ps(log_ratio, _mm256_mul_ps(drift, T));
    const __m256 sqrt_t = _mm256_sqrt_ps(T);
    const __m256 denominator = _mm256_mul_ps(v, sqrt_t);
    const __m256 d1 = _mm256_div_ps(numerator, denominator);
    const __m256 d2 = _mm256_sub_ps(d1, _mm256_mul_ps(v, sqrt_t));

    const __m256 negative_r = _mm256_sub_ps(zero, r);
    const __m256 discount_arg = _mm256_mul_ps(negative_r, T);
    const __m256 discount = avx_exp8(discount_arg);
    const __m256 cnd1 = avx_cnd8(d1);
    const __m256 cnd2 = avx_cnd8(d2);
    const __m256 call_value = _mm256_mul_ps(S, cnd1);
    const __m256 put_value = _mm256_mul_ps(_mm256_mul_ps(X, discount), cnd2);
    _mm256_storeu_ps(result + i, _mm256_sub_ps(call_value, put_value));
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

static void black_scholes_with_threads(
    float Sa[], float Xa[], float Ta[], float ra[], float va[], float result[], int count, int threads) {
    int i = 0;
#if defined(__AVX2__)
    if (count > 0) {
        const int vector_count = count - count % 8;
        const int vector_blocks = vector_count / 8;
        if (threads > 1 && count / threads >= 8192) {
#pragma omp parallel for schedule(static) num_threads(threads)
            for (int block = 0; block < vector_blocks; ++block)
                black_scholes_avx2_block(Sa, Xa, Ta, ra, va, result, block);
        } else {
            for (int block = 0; block < vector_blocks; ++block)
                black_scholes_avx2_block(Sa, Xa, Ta, ra, va, result, block);
        }
        i = vector_count;
    }
#endif
    for (; i < count; ++i) {
        float S = Sa[i], X = Xa[i];
        float T = Ta[i], r = ra[i];
        float v = va[i];

        float d1 = (logf(S / X) + (r + v * v * .5f) * T) / (v * sqrtf(T));
        float d2 = d1 - v * sqrtf(T);

        result[i] = S * CND(d1) - X * expf(-r * T) * CND(d2);
    }
}

void black_scholes_serial(float Sa[], float Xa[], float Ta[], float ra[], float va[], float result[], int count) {
    black_scholes_with_threads(Sa, Xa, Ta, ra, va, result, count, 1);
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

extern "C" void run(const void* input1,const void* input2,void* output,int n,int parameter,int threads)
{
    float* a = (float*)input1;
    black_scholes_with_threads(a, a + n, a + 2 * n, a + 3 * n, a + 4 * n, (float*)output, n, threads);
}
