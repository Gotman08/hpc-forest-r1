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
#include <cfloat>
#include <cstdint>
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
// Bounds checks keep inputs outside the approximation's safe range on the
// original scalar implementation. Comparisons also reject NaNs and infinities.
static inline bool bs8_all_between(__m256 x, float lower, float upper) {
    const __m256 ge = _mm256_cmp_ps(x, _mm256_set1_ps(lower), _CMP_GE_OQ);
    const __m256 le = _mm256_cmp_ps(x, _mm256_set1_ps(upper), _CMP_LE_OQ);
    return _mm256_movemask_ps(_mm256_and_ps(ge, le)) == 0xff;
}

// Natural logarithm for positive, normal float lanes. Mantissas are reduced
// around one and evaluated with the atanh series; callers guard the domain.
static inline __m256 bs8_log(__m256 x) {
    const __m256i bits = _mm256_castps_si256(x);
    __m256i exponent = _mm256_sub_epi32(
        _mm256_and_si256(_mm256_srli_epi32(bits, 23), _mm256_set1_epi32(0xff)),
        _mm256_set1_epi32(127));
    const __m256 mantissa_bits = _mm256_castsi256_ps(_mm256_or_si256(
        _mm256_and_si256(bits, _mm256_set1_epi32(0x007fffff)),
        _mm256_set1_epi32(0x3f800000)));
    const __m256 above_sqrt2 = _mm256_cmp_ps(
        mantissa_bits, _mm256_set1_ps(1.4142135623730951f), _CMP_GT_OQ);
    const __m256 m = _mm256_blendv_ps(
        mantissa_bits, _mm256_mul_ps(mantissa_bits, _mm256_set1_ps(0.5f)), above_sqrt2);
    exponent = _mm256_add_epi32(exponent, _mm256_and_si256(
        _mm256_castps_si256(above_sqrt2), _mm256_set1_epi32(1)));

    const __m256 z = _mm256_div_ps(
        _mm256_sub_ps(m, _mm256_set1_ps(1.f)),
        _mm256_add_ps(m, _mm256_set1_ps(1.f)));
    const __m256 z2 = _mm256_mul_ps(z, z);
    __m256 p = _mm256_set1_ps(1.f / 11.f);
    p = _mm256_add_ps(_mm256_set1_ps(1.f / 9.f), _mm256_mul_ps(z2, p));
    p = _mm256_add_ps(_mm256_set1_ps(1.f / 7.f), _mm256_mul_ps(z2, p));
    p = _mm256_add_ps(_mm256_set1_ps(1.f / 5.f), _mm256_mul_ps(z2, p));
    p = _mm256_add_ps(_mm256_set1_ps(1.f / 3.f), _mm256_mul_ps(z2, p));
    p = _mm256_add_ps(_mm256_set1_ps(1.f), _mm256_mul_ps(z2, p));
    const __m256 log_m = _mm256_mul_ps(_mm256_set1_ps(2.f), _mm256_mul_ps(z, p));
    const __m256 e = _mm256_cvtepi32_ps(exponent);
    return _mm256_add_ps(log_m, _mm256_mul_ps(e, _mm256_set1_ps(0.6931471805599453f)));
}

// Exponential for finite lanes in [-80, 80]. Range reduction leaves a small
// residual for a degree-seven polynomial; guarded callers use libm otherwise.
static inline __m256 bs8_exp(__m256 x) {
    const __m256 y = _mm256_mul_ps(x, _mm256_set1_ps(1.4426950408889634f));
    const __m256 rounded = _mm256_round_ps(
        y, _MM_FROUND_TO_NEAREST_INT | _MM_FROUND_NO_EXC);
    const __m256i exponent = _mm256_cvttps_epi32(rounded);
    const __m256 r = _mm256_sub_ps(
        x, _mm256_mul_ps(rounded, _mm256_set1_ps(0.6931471805599453f)));

    __m256 p = _mm256_set1_ps(1.f / 5040.f);
    p = _mm256_add_ps(_mm256_set1_ps(1.f / 720.f), _mm256_mul_ps(r, p));
    p = _mm256_add_ps(_mm256_set1_ps(1.f / 120.f), _mm256_mul_ps(r, p));
    p = _mm256_add_ps(_mm256_set1_ps(1.f / 24.f), _mm256_mul_ps(r, p));
    p = _mm256_add_ps(_mm256_set1_ps(1.f / 6.f), _mm256_mul_ps(r, p));
    p = _mm256_add_ps(_mm256_set1_ps(0.5f), _mm256_mul_ps(r, p));
    p = _mm256_add_ps(_mm256_set1_ps(1.f), _mm256_mul_ps(r, p));
    p = _mm256_add_ps(_mm256_set1_ps(1.f), _mm256_mul_ps(r, p));

    const __m256i scale_bits = _mm256_slli_epi32(
        _mm256_add_epi32(exponent, _mm256_set1_epi32(127)), 23);
    return _mm256_mul_ps(p, _mm256_castsi256_ps(scale_bits));
}

static inline __m256 bs8_cnd(__m256 x) {
    const __m256 abs_mask = _mm256_castsi256_ps(_mm256_set1_epi32(0x7fffffff));
    const __m256 L = _mm256_and_ps(x, abs_mask);
    const __m256 k = _mm256_div_ps(
        _mm256_set1_ps(1.f),
        _mm256_add_ps(_mm256_set1_ps(1.f), _mm256_mul_ps(_mm256_set1_ps(0.2316419f), L)));

    // Evaluate the CND polynomial in Horner form to reduce intermediate powers
    // and live vector values; retain the same coefficients and approximation.
    __m256 w = _mm256_set1_ps(1.330274429f);
    w = _mm256_add_ps(_mm256_set1_ps(-1.821255978f), _mm256_mul_ps(k, w));
    w = _mm256_add_ps(_mm256_set1_ps(1.781477937f), _mm256_mul_ps(k, w));
    w = _mm256_add_ps(_mm256_set1_ps(-0.356563782f), _mm256_mul_ps(k, w));
    w = _mm256_add_ps(_mm256_set1_ps(0.31938153f), _mm256_mul_ps(k, w));
    w = _mm256_mul_ps(k, w);

    const __m256 exp_arg = _mm256_mul_ps(
        _mm256_mul_ps(_mm256_sub_ps(_mm256_setzero_ps(), L), L), _mm256_set1_ps(0.5f));
    w = _mm256_mul_ps(w, _mm256_mul_ps(
        _mm256_set1_ps(0.39894228040f), bs8_exp(exp_arg)));
    const __m256 positive = _mm256_cmp_ps(x, _mm256_setzero_ps(), _CMP_GT_OQ);
    return _mm256_blendv_ps(w, _mm256_sub_ps(_mm256_set1_ps(1.f), w), positive);
}

static inline void black_scholes_avx2(float Sa[], float Xa[], float Ta[], float ra[],
                                      float va[], float result[], int count) {
    int i = 0;
    for (; count - i >= 8; i += 8) {
        const __m256 S = _mm256_loadu_ps(Sa + i);
        const __m256 X = _mm256_loadu_ps(Xa + i);
        const __m256 T = _mm256_loadu_ps(Ta + i);
        const __m256 r = _mm256_loadu_ps(ra + i);
        const __m256 v = _mm256_loadu_ps(va + i);

        // Combine the input-lane tests so the common valid path needs only one
        // mask extraction and one branch before entering the vector math.
        const __m256 positive_lower = _mm256_set1_ps(FLT_MIN);
        const __m256 positive_upper = _mm256_set1_ps(FLT_MAX);
        __m256 valid_inputs = _mm256_cmp_ps(S, positive_lower, _CMP_GE_OQ);
        valid_inputs = _mm256_and_ps(valid_inputs,
                                     _mm256_cmp_ps(S, positive_upper, _CMP_LE_OQ));
        valid_inputs = _mm256_and_ps(valid_inputs,
                                     _mm256_cmp_ps(X, positive_lower, _CMP_GE_OQ));
        valid_inputs = _mm256_and_ps(valid_inputs,
                                     _mm256_cmp_ps(X, positive_upper, _CMP_LE_OQ));
        valid_inputs = _mm256_and_ps(valid_inputs,
                                     _mm256_cmp_ps(T, positive_lower, _CMP_GE_OQ));
        valid_inputs = _mm256_and_ps(valid_inputs,
                                     _mm256_cmp_ps(T, positive_upper, _CMP_LE_OQ));
        valid_inputs = _mm256_and_ps(valid_inputs,
                                     _mm256_cmp_ps(v, positive_lower, _CMP_GE_OQ));
        valid_inputs = _mm256_and_ps(valid_inputs,
                                     _mm256_cmp_ps(v, positive_upper, _CMP_LE_OQ));
        valid_inputs = _mm256_and_ps(valid_inputs,
                                     _mm256_cmp_ps(r, _mm256_set1_ps(-FLT_MAX), _CMP_GE_OQ));
        valid_inputs = _mm256_and_ps(valid_inputs,
                                     _mm256_cmp_ps(r, positive_upper, _CMP_LE_OQ));
        if (_mm256_movemask_ps(valid_inputs) != 0xff) {
            black_scholes_serial(Sa + i, Xa + i, Ta + i, ra + i, va + i, result + i, 8);
            continue;
        }

        const __m256 ratio = _mm256_div_ps(S, X);
        if (!bs8_all_between(ratio, FLT_MIN, FLT_MAX)) {
            black_scholes_serial(Sa + i, Xa + i, Ta + i, ra + i, va + i, result + i, 8);
            continue;
        }

        const __m256 sqrtT = _mm256_sqrt_ps(T);
        const __m256 v2half = _mm256_mul_ps(_mm256_mul_ps(v, v), _mm256_set1_ps(0.5f));
        const __m256 d1 = _mm256_div_ps(
            _mm256_add_ps(bs8_log(ratio),
                          _mm256_mul_ps(_mm256_add_ps(r, v2half), T)),
            _mm256_mul_ps(v, sqrtT));
        const __m256 d2 = _mm256_sub_ps(d1, _mm256_mul_ps(v, sqrtT));
        const __m256 abs_d1 = _mm256_and_ps(
            d1, _mm256_castsi256_ps(_mm256_set1_epi32(0x7fffffff)));
        const __m256 abs_d2 = _mm256_and_ps(
            d2, _mm256_castsi256_ps(_mm256_set1_epi32(0x7fffffff)));
        const __m256 cnd_arg1 = _mm256_mul_ps(
            _mm256_mul_ps(_mm256_sub_ps(_mm256_setzero_ps(), abs_d1), abs_d1),
            _mm256_set1_ps(0.5f));
        const __m256 cnd_arg2 = _mm256_mul_ps(
            _mm256_mul_ps(_mm256_sub_ps(_mm256_setzero_ps(), abs_d2), abs_d2),
            _mm256_set1_ps(0.5f));
        const __m256 exp_arg = _mm256_mul_ps(_mm256_sub_ps(_mm256_setzero_ps(), r), T);
        if (!bs8_all_between(d1, -FLT_MAX, FLT_MAX) ||
            !bs8_all_between(d2, -FLT_MAX, FLT_MAX) ||
            !bs8_all_between(cnd_arg1, -80.f, 0.f) ||
            !bs8_all_between(cnd_arg2, -80.f, 0.f) ||
            !bs8_all_between(exp_arg, -80.f, 80.f)) {
            black_scholes_serial(Sa + i, Xa + i, Ta + i, ra + i, va + i, result + i, 8);
            continue;
        }

        const __m256 value = _mm256_sub_ps(
            _mm256_mul_ps(S, bs8_cnd(d1)),
            _mm256_mul_ps(_mm256_mul_ps(X, bs8_exp(exp_arg)), bs8_cnd(d2)));
        _mm256_storeu_ps(result + i, value);
    }

    if (i < count)
        black_scholes_serial(Sa + i, Xa + i, Ta + i, ra + i, va + i, result + i, count - i);
}
#endif

static inline void black_scholes_kernel(float Sa[], float Xa[], float Ta[], float ra[],
                                        float va[], float result[], int count) {
#if defined(__AVX2__)
    black_scholes_avx2(Sa, Xa, Ta, ra, va, result, count);
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

extern "C" void run(const void* input1, const void* input2, void* output,
                    int n, int parameter, int threads) {
    (void)input2;
    (void)parameter;

    if (n <= 0)
        return;

    float* a = (float*)input1;
    float* result = (float*)output;
    float* S = a;
    float* X = a + n;
    float* T = a + 2 * n;
    float* r = a + 3 * n;
    float* v = a + 4 * n;

    if (threads <= 1 || n == 1) {
        black_scholes_kernel(S, X, T, r, v, result, n);
        return;
    }

    const int team_request = std::min(threads, n);
#pragma omp parallel num_threads(team_request)
    {
        const int tid = omp_get_thread_num();
        const int team_count = omp_get_num_threads();
        const int begin = static_cast<int>((static_cast<std::int64_t>(tid) * n) / team_count);
        const int end = static_cast<int>((static_cast<std::int64_t>(tid + 1) * n) / team_count);
        black_scholes_kernel(S + begin, X + begin, T + begin, r + begin, v + begin,
                             result + begin, end - begin);
    }
}
