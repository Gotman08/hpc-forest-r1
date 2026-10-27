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
#endif
#include <algorithm>
#include <cfloat>
#include <cmath>
#include <cstdint>
#include <math.h>
#include <omp.h>
#if (defined(__GNUC__) || defined(__clang__)) && (defined(__x86_64__) || defined(__i386__))
#include <immintrin.h>
#define BS_HAVE_TARGET_AVX2 1
#define BS_TARGET_AVX2 __attribute__((target("avx2,fma")))
#else
#define BS_HAVE_TARGET_AVX2 0
#endif

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
    if (X > 0.f) w = 1.f - w;
    return w;
}

static inline float black_scholes_one(float S, float X, float T, float r, float v) {
    float d1 = (logf(S / X) + (r + v * v * .5f) * T) / (v * sqrtf(T));
    float d2 = d1 - v * sqrtf(T);
    return S * CND(d1) - X * expf(-r * T) * CND(d2);
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

static void black_scholes_compiler_simd_range(const float *Sa, const float *Xa,
                                               const float *Ta, const float *ra,
                                               const float *va, float *result,
                                               int begin, int end) {
#pragma omp simd
    for (int i = begin; i < end; ++i) {
        float S = Sa[i], X = Xa[i];
        float T = Ta[i], r = ra[i];
        float v = va[i];
        float d1 = (logf(S / X) + (r + v * v * .5f) * T) / (v * sqrtf(T));
        float d2 = d1 - v * sqrtf(T);
        result[i] = S * CND(d1) - X * expf(-r * T) * CND(d2);
    }
}

#if BS_HAVE_TARGET_AVX2
static BS_TARGET_AVX2 inline bool avx2_all_between(__m256 x, float lo, float hi) {
    const __m256 low = _mm256_set1_ps(lo);
    const __m256 high = _mm256_set1_ps(hi);
    const __m256 ge = _mm256_cmp_ps(x, low, _CMP_GE_OQ);
    const __m256 le = _mm256_cmp_ps(x, high, _CMP_LE_OQ);
    return _mm256_movemask_ps(_mm256_and_ps(ge, le)) == 0xff;
}

static BS_TARGET_AVX2 inline __m256 avx2_exp_approx(__m256 x) {
    const __m256 log2e = _mm256_set1_ps(1.4426950408889634f);
    const __m256 z = _mm256_mul_ps(x, log2e);
    const __m256 rounded = _mm256_round_ps(z, _MM_FROUND_TO_NEAREST_INT | _MM_FROUND_NO_EXC);
    const __m256i k = _mm256_cvttps_epi32(rounded);
    const __m256 kf = _mm256_cvtepi32_ps(k);
    __m256 r = _mm256_fmadd_ps(kf, _mm256_set1_ps(-0.693359375f), x);
    r = _mm256_fmadd_ps(kf, _mm256_set1_ps(0.00021219444005469058f), r);
    __m256 p = _mm256_set1_ps(1.0f / 5040.0f);
    p = _mm256_fmadd_ps(p, r, _mm256_set1_ps(1.0f / 720.0f));
    p = _mm256_fmadd_ps(p, r, _mm256_set1_ps(1.0f / 120.0f));
    p = _mm256_fmadd_ps(p, r, _mm256_set1_ps(1.0f / 24.0f));
    p = _mm256_fmadd_ps(p, r, _mm256_set1_ps(1.0f / 6.0f));
    p = _mm256_fmadd_ps(p, r, _mm256_set1_ps(0.5f));
    p = _mm256_fmadd_ps(p, r, _mm256_set1_ps(1.0f));
    p = _mm256_fmadd_ps(p, r, _mm256_set1_ps(1.0f));
    const __m256i pow2_bits = _mm256_slli_epi32(_mm256_add_epi32(k, _mm256_set1_epi32(127)), 23);
    return _mm256_mul_ps(p, _mm256_castsi256_ps(pow2_bits));
}

static BS_TARGET_AVX2 inline __m256 avx2_log_approx(__m256 x) {
    const __m256i bits = _mm256_castps_si256(x);
    const __m256i exponent_bits = _mm256_and_si256(bits, _mm256_set1_epi32(0x7f800000));
    __m256i exponent = _mm256_sub_epi32(_mm256_srli_epi32(exponent_bits, 23), _mm256_set1_epi32(127));
    const __m256i mantissa_bits = _mm256_or_si256(_mm256_and_si256(bits, _mm256_set1_epi32(0x007fffff)), _mm256_set1_epi32(0x3f800000));
    __m256 mantissa = _mm256_castsi256_ps(mantissa_bits);
    const __m256 adjust = _mm256_cmp_ps(mantissa, _mm256_set1_ps(1.4142135623730951f), _CMP_GT_OQ);
    const __m256i adjust_i = _mm256_and_si256(_mm256_castps_si256(adjust), _mm256_set1_epi32(1));
    exponent = _mm256_add_epi32(exponent, adjust_i);
    mantissa = _mm256_blendv_ps(mantissa, _mm256_mul_ps(mantissa, _mm256_set1_ps(0.5f)), adjust);
    const __m256 y = _mm256_div_ps(_mm256_sub_ps(mantissa, _mm256_set1_ps(1.0f)), _mm256_add_ps(mantissa, _mm256_set1_ps(1.0f)));
    const __m256 y2 = _mm256_mul_ps(y, y);
    __m256 p = _mm256_set1_ps(1.0f / 9.0f);
    p = _mm256_fmadd_ps(p, y2, _mm256_set1_ps(1.0f / 7.0f));
    p = _mm256_fmadd_ps(p, y2, _mm256_set1_ps(1.0f / 5.0f));
    p = _mm256_fmadd_ps(p, y2, _mm256_set1_ps(1.0f / 3.0f));
    p = _mm256_fmadd_ps(p, y2, _mm256_set1_ps(1.0f));
    const __m256 log_mantissa = _mm256_mul_ps(_mm256_mul_ps(_mm256_set1_ps(2.0f), y), p);
    return _mm256_fmadd_ps(_mm256_cvtepi32_ps(exponent), _mm256_set1_ps(0.6931471805599453f), log_mantissa);
}

static BS_TARGET_AVX2 inline __m256 avx2_cnd_approx(__m256 x) {
    const __m256 sign = _mm256_castsi256_ps(_mm256_set1_epi32(0x80000000));
    const __m256 l = _mm256_andnot_ps(sign, x);
    const __m256 k = _mm256_div_ps(_mm256_set1_ps(1.0f), _mm256_add_ps(_mm256_set1_ps(1.0f), _mm256_mul_ps(_mm256_set1_ps(0.2316419f), l)));
    __m256 p = _mm256_set1_ps(1.330274429f);
    p = _mm256_fmadd_ps(p, k, _mm256_set1_ps(-1.821255978f));
    p = _mm256_fmadd_ps(p, k, _mm256_set1_ps(1.781477937f));
    p = _mm256_fmadd_ps(p, k, _mm256_set1_ps(-0.356563782f));
    p = _mm256_fmadd_ps(p, k, _mm256_set1_ps(0.31938153f));
    p = _mm256_mul_ps(p, k);
    const __m256 cnd_exp = _mm256_mul_ps(_mm256_set1_ps(-0.5f), _mm256_mul_ps(l, l));
    __m256 w = _mm256_mul_ps(p, _mm256_set1_ps(0.39894228040f));
    w = _mm256_mul_ps(w, avx2_exp_approx(cnd_exp));
    const __m256 positive = _mm256_cmp_ps(x, _mm256_setzero_ps(), _CMP_GT_OQ);
    return _mm256_blendv_ps(w, _mm256_sub_ps(_mm256_set1_ps(1.0f), w), positive);
}

static BS_TARGET_AVX2 bool avx2_try_block(const float *Sa, const float *Xa, const float *Ta, const float *ra, const float *va, float *result, int i) {
    const __m256 zero = _mm256_setzero_ps();
    const __m256 s = _mm256_loadu_ps(Sa + i);
    const __m256 x = _mm256_loadu_ps(Xa + i);
    const __m256 t = _mm256_loadu_ps(Ta + i);
    const __m256 r = _mm256_loadu_ps(ra + i);
    const __m256 v = _mm256_loadu_ps(va + i);
    if (!avx2_all_between(s, FLT_MIN, FLT_MAX) || !avx2_all_between(x, FLT_MIN, FLT_MAX) ||
        !avx2_all_between(t, FLT_MIN, FLT_MAX) || !avx2_all_between(v, FLT_MIN, FLT_MAX) ||
        !avx2_all_between(_mm256_andnot_ps(_mm256_castsi256_ps(_mm256_set1_epi32(0x80000000)), r), 0.0f, FLT_MAX)) return false;
    const __m256 ratio = _mm256_div_ps(s, x);
    if (!avx2_all_between(ratio, FLT_MIN, FLT_MAX)) return false;
    const __m256 root_t = _mm256_sqrt_ps(t);
    const __m256 denom = _mm256_mul_ps(v, root_t);
    if (!avx2_all_between(denom, FLT_MIN, FLT_MAX)) return false;
    const __m256 log_ratio = avx2_log_approx(ratio);
    const __m256 vv = _mm256_mul_ps(v, v);
    const __m256 drift = _mm256_mul_ps(_mm256_add_ps(r, _mm256_mul_ps(vv, _mm256_set1_ps(0.5f))), t);
    const __m256 d1 = _mm256_div_ps(_mm256_add_ps(log_ratio, drift), denom);
    const __m256 d2 = _mm256_sub_ps(d1, denom);
    if (!avx2_all_between(d1, -FLT_MAX, FLT_MAX) || !avx2_all_between(d2, -FLT_MAX, FLT_MAX)) return false;
    const __m256 discount_arg = _mm256_mul_ps(_mm256_sub_ps(zero, r), t);
    const __m256 d1_arg = _mm256_mul_ps(_mm256_set1_ps(-0.5f), _mm256_mul_ps(d1, d1));
    const __m256 d2_arg = _mm256_mul_ps(_mm256_set1_ps(-0.5f), _mm256_mul_ps(d2, d2));
    if (!avx2_all_between(discount_arg, -80.0f, 80.0f) || !avx2_all_between(d1_arg, -80.0f, 0.0f) || !avx2_all_between(d2_arg, -80.0f, 0.0f)) return false;
    const __m256 discount = avx2_exp_approx(discount_arg);
    const __m256 cnd1 = avx2_cnd_approx(d1);
    const __m256 cnd2 = avx2_cnd_approx(d2);
    const __m256 value = _mm256_sub_ps(_mm256_mul_ps(s, cnd1), _mm256_mul_ps(_mm256_mul_ps(x, discount), cnd2));
    if (!avx2_all_between(value, -FLT_MAX, FLT_MAX)) return false;
    _mm256_storeu_ps(result + i, value);
    return true;
}

static BS_TARGET_AVX2 void black_scholes_avx2_range(const float *Sa, const float *Xa, const float *Ta, const float *ra, const float *va, float *result, int begin, int end) {
    int i = begin;
    for (; end - i >= 8; i += 8) {
        if (!avx2_try_block(Sa, Xa, Ta, ra, va, result, i)) {
            for (int lane = 0; lane < 8; ++lane)
                result[i + lane] = black_scholes_one(Sa[i + lane], Xa[i + lane], Ta[i + lane], ra[i + lane], va[i + lane]);
        }
    }
    for (; i < end; ++i)
        result[i] = black_scholes_one(Sa[i], Xa[i], Ta[i], ra[i], va[i]);
}

static bool black_scholes_avx2_available() {
    __builtin_cpu_init();
    return __builtin_cpu_supports("avx2") && __builtin_cpu_supports("fma");
}
#endif

extern "C" void run(const void *input1, const void *input2, void *output, int n, int parameter, int threads) {
    (void)input2;
    (void)parameter;
    if (n <= 0) return;
    const float *a = static_cast<const float *>(input1);
    float *result = static_cast<float *>(output);
    const size_t count = static_cast<size_t>(n);
    const float *Sa = a;
    const float *Xa = a + count;
    const float *Ta = a + 2 * count;
    const float *ra = a + 3 * count;
    const float *va = a + 4 * count;
    const int worker_count = threads > 1 ? std::min(threads, n) : 1;
    const bool use_parallel = worker_count > 1 && static_cast<long long>(n) >= 1024LL * worker_count;
#if BS_HAVE_TARGET_AVX2
    const bool use_avx2 = black_scholes_avx2_available();
#else
    const bool use_avx2 = false;
#endif
    if (!use_parallel) {
#if BS_HAVE_TARGET_AVX2
        if (use_avx2) {
            black_scholes_avx2_range(Sa, Xa, Ta, ra, va, result, 0, n);
            return;
        }
#endif
        black_scholes_compiler_simd_range(Sa, Xa, Ta, ra, va, result, 0, n);
        return;
    }
#if BS_HAVE_TARGET_AVX2
    if (use_avx2) {
#pragma omp parallel num_threads(worker_count)
        {
            const int tid = omp_get_thread_num();
            const int team = omp_get_num_threads();
            const int begin = static_cast<int>((static_cast<long long>(n) * tid) / team);
            const int end = static_cast<int>((static_cast<long long>(n) * (tid + 1)) / team);
            black_scholes_avx2_range(Sa, Xa, Ta, ra, va, result, begin, end);
        }
        return;
    }
#endif
#pragma omp parallel num_threads(worker_count)
    {
        const int tid = omp_get_thread_num();
        const int team = omp_get_num_threads();
        const int begin = static_cast<int>((static_cast<long long>(n) * tid) / team);
        const int end = static_cast<int>((static_cast<long long>(n) * (tid + 1)) / team);
        black_scholes_compiler_simd_range(Sa, Xa, Ta, ra, va, result, begin, end);
    }
}
