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
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <cstring>
#include <math.h>
#include <omp.h>

#if (defined(__GNUC__) || defined(__clang__)) && defined(__AVX__)
#include <immintrin.h>
#define BLACK_SCHOLES_AVX_CND 1
#else
#define BLACK_SCHOLES_AVX_CND 0
#endif

#if BLACK_SCHOLES_AVX_CND && defined(__AVX2__)
#define BLACK_SCHOLES_AVX2_MATH 1
#else
#define BLACK_SCHOLES_AVX2_MATH 0
#endif

// Cumulative normal distribution function.
static inline float CND(float X) {
    float L = fabsf(X);
    float k = 1.f / (1.f + 0.2316419f * L);

    float poly = 1.330274429f;
    poly = poly * k - 1.821255978f;
    poly = poly * k + 1.781477937f;
    poly = poly * k - 0.356563782f;
    poly = poly * k + 0.31938153f;

    const float invSqrt2Pi = 0.39894228040f;
    float w = k * poly;
    w *= invSqrt2Pi * expf(-L * L * .5f);
    if (X > 0.f)
        w = 1.f - w;
    return w;
}

static inline float black_scholes_one(float S, float X, float T, float r, float v) {
    float d1 = (logf(S / X) + (r + v * v * .5f) * T) / (v * sqrtf(T));
    float d2 = d1 - v * sqrtf(T);
    return S * CND(d1) - X * expf(-r * T) * CND(d2);
}

#if BLACK_SCHOLES_AVX_CND
// Range-reduced exp approximation. The caller bounds the input to [-32, 8].
static inline __m256 exp_reduced_range8(__m256 x) {
    const __m256 log2e = _mm256_set1_ps(1.4426950408889634f);
    const __m256 ln2 = _mm256_set1_ps(0.6931471805599453f);
    __m256 exponent_f = _mm256_round_ps(
        _mm256_mul_ps(x, log2e),
        _MM_FROUND_TO_NEAREST_INT | _MM_FROUND_NO_EXC);
    __m256i exponent_i = _mm256_cvttps_epi32(exponent_f);
    __m256 reduced = _mm256_sub_ps(x, _mm256_mul_ps(exponent_f, ln2));

    __m256 p = _mm256_set1_ps(1.f / 5040.f);
    p = _mm256_add_ps(_mm256_mul_ps(p, reduced), _mm256_set1_ps(1.f / 720.f));
    p = _mm256_add_ps(_mm256_mul_ps(p, reduced), _mm256_set1_ps(1.f / 120.f));
    p = _mm256_add_ps(_mm256_mul_ps(p, reduced), _mm256_set1_ps(1.f / 24.f));
    p = _mm256_add_ps(_mm256_mul_ps(p, reduced), _mm256_set1_ps(1.f / 6.f));
    p = _mm256_add_ps(_mm256_mul_ps(p, reduced), _mm256_set1_ps(0.5f));
    p = _mm256_add_ps(_mm256_mul_ps(p, reduced), _mm256_set1_ps(1.f));
    __m256 exp_reduced = _mm256_add_ps(_mm256_mul_ps(p, reduced), _mm256_set1_ps(1.f));

#if BLACK_SCHOLES_AVX2_MATH
    const __m256i biased_exponent = _mm256_add_epi32(exponent_i, _mm256_set1_epi32(127));
    const __m256i scale_bits = _mm256_slli_epi32(biased_exponent, 23);
    const __m256 scale = _mm256_castsi256_ps(scale_bits);
#else
    std::int32_t exponent_lanes[8];
    float scale_lanes[8];
    _mm256_storeu_si256(reinterpret_cast<__m256i*>(exponent_lanes), exponent_i);
    for (int lane = 0; lane < 8; ++lane) {
        const std::uint32_t bits =
            static_cast<std::uint32_t>(exponent_lanes[lane] + 127) << 23;
        std::memcpy(&scale_lanes[lane], &bits, sizeof(bits));
    }
    const __m256 scale = _mm256_loadu_ps(scale_lanes);
#endif
    return _mm256_mul_ps(exp_reduced, scale);
}

static inline __m256 cnd_approx_vector8(__m256 xv) {
    const __m256 sign_mask = _mm256_set1_ps(-0.0f);
    const __m256 L = _mm256_andnot_ps(sign_mask, xv);
    const __m256 one = _mm256_set1_ps(1.f);
    const __m256 k = _mm256_div_ps(
        one, _mm256_add_ps(one, _mm256_mul_ps(_mm256_set1_ps(0.2316419f), L)));

    __m256 poly = _mm256_set1_ps(1.330274429f);
    poly = _mm256_sub_ps(
        _mm256_mul_ps(poly, k), _mm256_set1_ps(1.821255978f));
    poly = _mm256_add_ps(
        _mm256_mul_ps(poly, k), _mm256_set1_ps(1.781477937f));
    poly = _mm256_sub_ps(
        _mm256_mul_ps(poly, k), _mm256_set1_ps(0.356563782f));
    poly = _mm256_add_ps(
        _mm256_mul_ps(poly, k), _mm256_set1_ps(0.31938153f));
    __m256 w = _mm256_mul_ps(k, poly);

    const __m256 exponent = _mm256_mul_ps(
        _mm256_mul_ps(_mm256_sub_ps(_mm256_setzero_ps(), L), L),
        _mm256_set1_ps(0.5f));
    const __m256 factor = _mm256_mul_ps(
        _mm256_set1_ps(0.39894228040f), exp_reduced_range8(exponent));
    w = _mm256_mul_ps(w, factor);

    const __m256 positive = _mm256_cmp_ps(xv, _mm256_setzero_ps(), _CMP_GT_OQ);
    return _mm256_blendv_ps(w, _mm256_sub_ps(one, w), positive);
}

static inline __m256 cnd_approx8(const float* x) {
    return cnd_approx_vector8(_mm256_loadu_ps(x));
}
#endif

#if BLACK_SCHOLES_AVX2_MATH
// Input is positive, finite, and bounded before this normalized-mantissa log is used.
static inline __m256 log_positive_range8(__m256 x) {
    const __m256i bits = _mm256_castps_si256(x);
    const __m256i exponent_field = _mm256_and_si256(
        _mm256_srli_epi32(bits, 23), _mm256_set1_epi32(0xff));
    __m256i exponent = _mm256_sub_epi32(exponent_field, _mm256_set1_epi32(127));
    const __m256i mantissa_bits = _mm256_or_si256(
        _mm256_and_si256(bits, _mm256_set1_epi32(0x007fffff)),
        _mm256_set1_epi32(0x3f800000));
    __m256 mantissa = _mm256_castsi256_ps(mantissa_bits);

    const __m256 adjust = _mm256_cmp_ps(
        mantissa, _mm256_set1_ps(1.4142135623730951f), _CMP_GT_OQ);
    const __m256i adjust_i = _mm256_and_si256(
        _mm256_castps_si256(adjust), _mm256_set1_epi32(1));
    exponent = _mm256_add_epi32(exponent, adjust_i);
    mantissa = _mm256_blendv_ps(
        mantissa, _mm256_mul_ps(mantissa, _mm256_set1_ps(0.5f)), adjust);

    const __m256 z = _mm256_div_ps(
        _mm256_sub_ps(mantissa, _mm256_set1_ps(1.f)),
        _mm256_add_ps(mantissa, _mm256_set1_ps(1.f)));
    const __m256 z2 = _mm256_mul_ps(z, z);
    __m256 p = _mm256_set1_ps(1.f / 13.f);
    p = _mm256_add_ps(_mm256_set1_ps(1.f / 11.f), _mm256_mul_ps(z2, p));
    p = _mm256_add_ps(_mm256_set1_ps(1.f / 9.f), _mm256_mul_ps(z2, p));
    p = _mm256_add_ps(_mm256_set1_ps(1.f / 7.f), _mm256_mul_ps(z2, p));
    p = _mm256_add_ps(_mm256_set1_ps(1.f / 5.f), _mm256_mul_ps(z2, p));
    p = _mm256_add_ps(_mm256_set1_ps(1.f / 3.f), _mm256_mul_ps(z2, p));
    p = _mm256_add_ps(_mm256_set1_ps(1.f), _mm256_mul_ps(z2, p));
    const __m256 log_mantissa = _mm256_mul_ps(
        _mm256_mul_ps(_mm256_set1_ps(2.f), z), p);
    const __m256 exponent_f = _mm256_cvtepi32_ps(exponent);
    return _mm256_add_ps(
        log_mantissa,
        _mm256_mul_ps(exponent_f, _mm256_set1_ps(0.6931471805599453f)));
}
#endif

static inline void black_scholes_range(const float Sa[], const float Xa[],
                                       const float Ta[], const float ra[],
                                       const float va[], float result[],
                                       int begin, int end) {
    int i = begin;
#if BLACK_SCHOLES_AVX2_MATH
    for (; end - i >= 8; i += 8) {
        const __m256 s = _mm256_loadu_ps(Sa + i);
        const __m256 x = _mm256_loadu_ps(Xa + i);
        const __m256 t = _mm256_loadu_ps(Ta + i);
        const __m256 r = _mm256_loadu_ps(ra + i);
        const __m256 v = _mm256_loadu_ps(va + i);
        const __m256 zero = _mm256_setzero_ps();

        // Conservative bounds keep fast-math intermediates in safe ranges;
        // any rejected block uses the original scalar libm expression.
        __m256 input_ok = _mm256_and_ps(
            _mm256_cmp_ps(s, zero, _CMP_GT_OQ),
            _mm256_cmp_ps(s, _mm256_set1_ps(1.0e20f), _CMP_LE_OQ));
        input_ok = _mm256_and_ps(input_ok, _mm256_cmp_ps(x, zero, _CMP_GT_OQ));
        input_ok = _mm256_and_ps(
            input_ok, _mm256_cmp_ps(x, _mm256_set1_ps(1.0e20f), _CMP_LE_OQ));
        input_ok = _mm256_and_ps(
            input_ok, _mm256_cmp_ps(t, _mm256_set1_ps(1.0e-12f), _CMP_GT_OQ));
        input_ok = _mm256_and_ps(
            input_ok, _mm256_cmp_ps(t, _mm256_set1_ps(1.0e6f), _CMP_LE_OQ));
        input_ok = _mm256_and_ps(
            input_ok, _mm256_cmp_ps(r, _mm256_set1_ps(-100.f), _CMP_GE_OQ));
        input_ok = _mm256_and_ps(
            input_ok, _mm256_cmp_ps(r, _mm256_set1_ps(100.f), _CMP_LE_OQ));
        input_ok = _mm256_and_ps(
            input_ok, _mm256_cmp_ps(v, _mm256_set1_ps(1.0e-6f), _CMP_GT_OQ));
        input_ok = _mm256_and_ps(
            input_ok, _mm256_cmp_ps(v, _mm256_set1_ps(100.f), _CMP_LE_OQ));

        bool use_fast = _mm256_movemask_ps(input_ok) == 0xff;
        __m256 ratio = zero;
        __m256 discount_argument = zero;
        if (use_fast) {
            ratio = _mm256_div_ps(s, x);
            discount_argument = _mm256_mul_ps(_mm256_sub_ps(zero, r), t);
            __m256 range_ok = _mm256_and_ps(
                _mm256_cmp_ps(ratio, _mm256_set1_ps(0.125f), _CMP_GE_OQ),
                _mm256_cmp_ps(ratio, _mm256_set1_ps(8.f), _CMP_LE_OQ));
            range_ok = _mm256_and_ps(
                range_ok,
                _mm256_cmp_ps(discount_argument, _mm256_set1_ps(-8.f), _CMP_GE_OQ));
            range_ok = _mm256_and_ps(
                range_ok,
                _mm256_cmp_ps(discount_argument, _mm256_set1_ps(8.f), _CMP_LE_OQ));
            use_fast = _mm256_movemask_ps(range_ok) == 0xff;
        }

        if (use_fast) {
            const __m256 root_t = _mm256_sqrt_ps(t);
            const __m256 v_root_t = _mm256_mul_ps(v, root_t);
            const __m256 v2_half = _mm256_mul_ps(
                _mm256_mul_ps(v, v), _mm256_set1_ps(0.5f));
            const __m256 drift = _mm256_mul_ps(
                _mm256_add_ps(r, v2_half), t);
            const __m256 d1 = _mm256_div_ps(
                _mm256_add_ps(log_positive_range8(ratio), drift), v_root_t);
            const __m256 d2 = _mm256_sub_ps(d1, v_root_t);
            const __m256 abs_mask = _mm256_set1_ps(-0.0f);
            __m256 d_ok = _mm256_and_ps(
                _mm256_cmp_ps(_mm256_andnot_ps(abs_mask, d1),
                              _mm256_set1_ps(8.f), _CMP_LE_OQ),
                _mm256_cmp_ps(_mm256_andnot_ps(abs_mask, d2),
                              _mm256_set1_ps(8.f), _CMP_LE_OQ));
            use_fast = _mm256_movemask_ps(d_ok) == 0xff;

            if (use_fast) {
                const __m256 discount = exp_reduced_range8(discount_argument);
                const __m256 c1 = cnd_approx_vector8(d1);
                const __m256 c2 = cnd_approx_vector8(d2);
                const __m256 discounted_x = _mm256_mul_ps(x, discount);
                const __m256 values = _mm256_sub_ps(
                    _mm256_mul_ps(s, c1), _mm256_mul_ps(discounted_x, c2));
                _mm256_storeu_ps(result + i, values);
                continue;
            }
        }

        for (int lane = 0; lane < 8; ++lane) {
            const int index = i + lane;
            result[index] = black_scholes_one(
                Sa[index], Xa[index], Ta[index], ra[index], va[index]);
        }
    }
#elif BLACK_SCHOLES_AVX_CND
    for (; end - i >= 8; i += 8) {
        alignas(32) float S[8], X[8], T[8], r[8], v[8];
        alignas(32) float discount[8], d1[8], d2[8];
        const __m256 s_vector = _mm256_loadu_ps(Sa + i);
        const __m256 x_vector = _mm256_loadu_ps(Xa + i);
        const __m256 t_vector = _mm256_loadu_ps(Ta + i);
        const __m256 r_vector = _mm256_loadu_ps(ra + i);
        const __m256 v_vector = _mm256_loadu_ps(va + i);
        _mm256_store_ps(S, s_vector);
        _mm256_store_ps(X, x_vector);
        _mm256_store_ps(T, t_vector);
        _mm256_store_ps(r, r_vector);
        _mm256_store_ps(v, v_vector);

        bool use_vector_cnd = true;
        for (int lane = 0; lane < 8; ++lane) {
            const int index = i + lane;
            const float ratio = S[lane] / X[lane];
            const float root_t = sqrtf(T[lane]);
            d1[lane] = (logf(ratio) + (r[lane] + v[lane] * v[lane] * .5f) * T[lane]) /
                        (v[lane] * root_t);
            d2[lane] = d1[lane] - v[lane] * root_t;
            discount[lane] = expf(-r[lane] * T[lane]);
            if (!std::isfinite(S[lane]) || !std::isfinite(X[lane]) ||
                !std::isfinite(discount[lane]) || !std::isfinite(d1[lane]) ||
                !std::isfinite(d2[lane]) || fabsf(d1[lane]) > 8.f ||
                fabsf(d2[lane]) > 8.f) {
                use_vector_cnd = false;
            }
        }

        if (use_vector_cnd) {
            const __m256 c1 = cnd_approx8(d1);
            const __m256 c2 = cnd_approx8(d2);
            const __m256 disc = _mm256_loadu_ps(discount);
            const __m256 discounted_x = _mm256_mul_ps(x_vector, disc);
            const __m256 values = _mm256_sub_ps(
                _mm256_mul_ps(s_vector, c1), _mm256_mul_ps(discounted_x, c2));
            _mm256_storeu_ps(result + i, values);
        } else {
            for (int lane = 0; lane < 8; ++lane) {
                const int index = i + lane;
                result[index] = black_scholes_one(
                    Sa[index], Xa[index], Ta[index], ra[index], va[index]);
            }
        }
    }
#endif
    for (; i < end; ++i) {
        result[i] = black_scholes_one(Sa[i], Xa[i], Ta[i], ra[i], va[i]);
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

extern "C" void run(const void* input1, const void* input2, void* output,
                     int n, int parameter, int threads) {
    (void)input2;
    (void)parameter;
    if (n <= 0)
        return;

    const float* a = static_cast<const float*>(input1);
    const std::size_t stride = static_cast<std::size_t>(n);
    float* result = static_cast<float*>(output);
    const float* S = a;
    const float* X = a + stride;
    const float* T = a + 2 * stride;
    const float* r = a + 3 * stride;
    const float* v = a + 4 * stride;

    const int block_count = n / 8;
    if (threads <= 1 || block_count <= 1) {
        black_scholes_range(S, X, T, r, v, result, 0, n);
        return;
    }

    const int workers = threads < block_count ? threads : block_count;
#pragma omp parallel for schedule(static) num_threads(workers)
    for (int block = 0; block < block_count; ++block) {
        const int begin = block * 8;
        black_scholes_range(S, X, T, r, v, result, begin, begin + 8);
    }

    const int tail_begin = block_count * 8;
    if (tail_begin < n)
        black_scholes_range(S, X, T, r, v, result, tail_begin, n);
}
