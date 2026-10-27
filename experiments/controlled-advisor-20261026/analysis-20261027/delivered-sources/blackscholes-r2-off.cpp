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
#include <cstddef>
#include <math.h>
#include <omp.h>

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

static inline float black_scholes_one(float S, float X, float T, float r, float v) {
    float d1 = (logf(S / X) + (r + v * v * .5f) * T) / (v * sqrtf(T));
    float d2 = d1 - v * sqrtf(T);
    return S * CND(d1) - X * expf(-r * T) * CND(d2);
}

static void black_scholes_scalar_range(float Sa[], float Xa[], float Ta[], float ra[], float va[], float result[], int begin, int end) {
#ifdef _OPENMP
#pragma omp simd
#endif
    for (int i = begin; i < end; ++i)
        result[i] = black_scholes_one(Sa[i], Xa[i], Ta[i], ra[i], va[i]);
}

#if defined(__AVX2__)
#include <immintrin.h>

static inline __m256 bs_log8(__m256 x) {
    const __m256 one = _mm256_set1_ps(1.0f);
    const __m256 good = _mm256_and_ps(
        _mm256_cmp_ps(x, _mm256_set1_ps(FLT_MIN), _CMP_GE_OQ),
        _mm256_cmp_ps(x, _mm256_set1_ps(FLT_MAX), _CMP_LE_OQ));
    const __m256 xx = _mm256_blendv_ps(one, x, good);

    __m256i bits = _mm256_castps_si256(xx);
    __m256i exponent = _mm256_sub_epi32(
        _mm256_and_si256(_mm256_srli_epi32(bits, 23), _mm256_set1_epi32(255)),
        _mm256_set1_epi32(127));
    const __m256i mantissa_bits = _mm256_or_si256(
        _mm256_and_si256(bits, _mm256_set1_epi32(0x007fffff)),
        _mm256_set1_epi32(0x3f800000));
    __m256 mantissa = _mm256_castsi256_ps(mantissa_bits);
    const __m256 adjust = _mm256_cmp_ps(mantissa, _mm256_set1_ps(1.41421356237f), _CMP_GT_OQ);
    mantissa = _mm256_blendv_ps(mantissa, _mm256_mul_ps(mantissa, _mm256_set1_ps(0.5f)), adjust);
    exponent = _mm256_add_epi32(exponent, _mm256_and_si256(_mm256_castps_si256(adjust), _mm256_set1_epi32(1)));

    const __m256 z = _mm256_div_ps(_mm256_sub_ps(mantissa, one), _mm256_add_ps(mantissa, one));
    const __m256 z2 = _mm256_mul_ps(z, z);
    __m256 p = _mm256_set1_ps(1.0f / 11.0f);
    p = _mm256_add_ps(_mm256_mul_ps(p, z2), _mm256_set1_ps(1.0f / 9.0f));
    p = _mm256_add_ps(_mm256_mul_ps(p, z2), _mm256_set1_ps(1.0f / 7.0f));
    p = _mm256_add_ps(_mm256_mul_ps(p, z2), _mm256_set1_ps(1.0f / 5.0f));
    p = _mm256_add_ps(_mm256_mul_ps(p, z2), _mm256_set1_ps(1.0f / 3.0f));
    const __m256 log_m = _mm256_mul_ps(_mm256_mul_ps(_mm256_set1_ps(2.0f), z),
                                       _mm256_add_ps(one, _mm256_mul_ps(z2, p)));
    const __m256 e = _mm256_cvtepi32_ps(exponent);
    __m256 y = _mm256_add_ps(log_m, _mm256_mul_ps(e, _mm256_set1_ps(0.693145751953125f)));
    y = _mm256_add_ps(y, _mm256_mul_ps(e, _mm256_set1_ps(1.428606765330187e-6f)));

    const int good_lanes = _mm256_movemask_ps(good);
    if (good_lanes != 0xff) {
        float in[8], out[8];
        _mm256_storeu_ps(in, x);
        _mm256_storeu_ps(out, y);
        for (int lane = 0; lane < 8; ++lane)
            if ((good_lanes & (1 << lane)) == 0)
                out[lane] = logf(in[lane]);
        y = _mm256_loadu_ps(out);
    }
    return y;
}

static inline __m256 bs_exp8(__m256 x) {
    const __m256 zero = _mm256_setzero_ps();
    const __m256 good = _mm256_and_ps(
        _mm256_cmp_ps(x, _mm256_set1_ps(-80.0f), _CMP_GE_OQ),
        _mm256_cmp_ps(x, _mm256_set1_ps(80.0f), _CMP_LE_OQ));
    const __m256 xx = _mm256_blendv_ps(zero, x, good);
    const __m256 t = _mm256_mul_ps(xx, _mm256_set1_ps(1.4426950408889634f));
    const __m256 rounded = _mm256_round_ps(t, _MM_FROUND_TO_NEAREST_INT | _MM_FROUND_NO_EXC);
    const __m256i n = _mm256_cvtps_epi32(rounded);
    const __m256 nf = _mm256_cvtepi32_ps(n);
    __m256 r = _mm256_sub_ps(xx, _mm256_mul_ps(nf, _mm256_set1_ps(0.693145751953125f)));
    r = _mm256_sub_ps(r, _mm256_mul_ps(nf, _mm256_set1_ps(1.428606765330187e-6f)));

    __m256 p = _mm256_set1_ps(1.0f / 5040.0f);
    p = _mm256_add_ps(_mm256_mul_ps(p, r), _mm256_set1_ps(1.0f / 720.0f));
    p = _mm256_add_ps(_mm256_mul_ps(p, r), _mm256_set1_ps(1.0f / 120.0f));
    p = _mm256_add_ps(_mm256_mul_ps(p, r), _mm256_set1_ps(1.0f / 24.0f));
    p = _mm256_add_ps(_mm256_mul_ps(p, r), _mm256_set1_ps(1.0f / 6.0f));
    p = _mm256_add_ps(_mm256_mul_ps(p, r), _mm256_set1_ps(0.5f));
    p = _mm256_add_ps(_mm256_mul_ps(p, r), _mm256_set1_ps(1.0f));
    p = _mm256_add_ps(_mm256_mul_ps(p, r), _mm256_set1_ps(1.0f));
    const __m256i scale_bits = _mm256_slli_epi32(_mm256_add_epi32(n, _mm256_set1_epi32(127)), 23);
    __m256 y = _mm256_mul_ps(p, _mm256_castsi256_ps(scale_bits));

    const int good_lanes = _mm256_movemask_ps(good);
    if (good_lanes != 0xff) {
        float in[8], out[8];
        _mm256_storeu_ps(in, x);
        _mm256_storeu_ps(out, y);
        for (int lane = 0; lane < 8; ++lane)
            if ((good_lanes & (1 << lane)) == 0)
                out[lane] = expf(in[lane]);
        y = _mm256_loadu_ps(out);
    }
    return y;
}

static inline __m256 bs_cnd8(__m256 x) {
    const __m256 zero = _mm256_setzero_ps();
    const __m256 one = _mm256_set1_ps(1.0f);
    const __m256 abs_mask = _mm256_castsi256_ps(_mm256_set1_epi32(0x7fffffff));
    const __m256 L = _mm256_and_ps(x, abs_mask);
    const __m256 k = _mm256_div_ps(one, _mm256_add_ps(one, _mm256_mul_ps(_mm256_set1_ps(0.2316419f), L)));
    __m256 p = _mm256_set1_ps(1.330274429f);
    p = _mm256_add_ps(_mm256_mul_ps(p, k), _mm256_set1_ps(-1.821255978f));
    p = _mm256_add_ps(_mm256_mul_ps(p, k), _mm256_set1_ps(1.781477937f));
    p = _mm256_add_ps(_mm256_mul_ps(p, k), _mm256_set1_ps(-0.356563782f));
    p = _mm256_add_ps(_mm256_mul_ps(p, k), _mm256_set1_ps(0.31938153f));
    p = _mm256_mul_ps(p, k);
    const __m256 density = bs_exp8(_mm256_mul_ps(_mm256_mul_ps(L, L), _mm256_set1_ps(-0.5f)));
    const __m256 w = _mm256_mul_ps(_mm256_mul_ps(p, _mm256_set1_ps(0.39894228040f)), density);
    return _mm256_blendv_ps(w, _mm256_sub_ps(one, w), _mm256_cmp_ps(x, zero, _CMP_GT_OQ));
}

static inline void bs_store_checked(float Sa[], float Xa[], float Ta[], float ra[], float va[],
                                    float result[], int offset, __m256 S, __m256 X,
                                    __m256 T, __m256 r, __m256 v, __m256 d1,
                                    __m256 d2, __m256 value) {
    _mm256_storeu_ps(result + offset, value);

    const __m256 fmin = _mm256_set1_ps(FLT_MIN);
    const __m256 fmax = _mm256_set1_ps(FLT_MAX);
    __m256 valid = _mm256_and_ps(
        _mm256_and_ps(_mm256_cmp_ps(S, fmin, _CMP_GE_OQ), _mm256_cmp_ps(S, fmax, _CMP_LE_OQ)),
        _mm256_and_ps(_mm256_cmp_ps(X, fmin, _CMP_GE_OQ), _mm256_cmp_ps(X, fmax, _CMP_LE_OQ)));
    valid = _mm256_and_ps(valid,
        _mm256_and_ps(_mm256_cmp_ps(T, fmin, _CMP_GE_OQ), _mm256_cmp_ps(T, fmax, _CMP_LE_OQ)));
    valid = _mm256_and_ps(valid,
        _mm256_and_ps(_mm256_cmp_ps(v, fmin, _CMP_GE_OQ), _mm256_cmp_ps(v, fmax, _CMP_LE_OQ)));
    valid = _mm256_and_ps(valid,
        _mm256_and_ps(_mm256_cmp_ps(r, _mm256_set1_ps(-FLT_MAX), _CMP_GE_OQ), _mm256_cmp_ps(r, fmax, _CMP_LE_OQ)));
    valid = _mm256_and_ps(valid,
        _mm256_and_ps(_mm256_cmp_ps(d1, _mm256_set1_ps(-FLT_MAX), _CMP_GE_OQ), _mm256_cmp_ps(d1, fmax, _CMP_LE_OQ)));
    valid = _mm256_and_ps(valid,
        _mm256_and_ps(_mm256_cmp_ps(d2, _mm256_set1_ps(-FLT_MAX), _CMP_GE_OQ), _mm256_cmp_ps(d2, fmax, _CMP_LE_OQ)));

    const int valid_lanes = _mm256_movemask_ps(valid);
    if (valid_lanes != 0xff) {
        float s[8], x[8], t[8], rate[8], vol[8];
        _mm256_storeu_ps(s, S);
        _mm256_storeu_ps(x, X);
        _mm256_storeu_ps(t, T);
        _mm256_storeu_ps(rate, r);
        _mm256_storeu_ps(vol, v);
        for (int lane = 0; lane < 8; ++lane)
            if ((valid_lanes & (1 << lane)) == 0)
                result[offset + lane] = black_scholes_one(s[lane], x[lane], t[lane], rate[lane], vol[lane]);
    }
}

static inline void black_scholes_avx2_one(float Sa[], float Xa[], float Ta[], float ra[], float va[],
                                          float result[], int offset) {
    const __m256 S = _mm256_loadu_ps(Sa + offset);
    const __m256 X = _mm256_loadu_ps(Xa + offset);
    const __m256 T = _mm256_loadu_ps(Ta + offset);
    const __m256 r = _mm256_loadu_ps(ra + offset);
    const __m256 v = _mm256_loadu_ps(va + offset);
    const __m256 ratio = _mm256_div_ps(S, X);
    const __m256 root_t = _mm256_sqrt_ps(T);
    const __m256 vt = _mm256_mul_ps(v, root_t);
    const __m256 drift = _mm256_mul_ps(_mm256_add_ps(r, _mm256_mul_ps(_mm256_mul_ps(v, v), _mm256_set1_ps(0.5f))), T);
    const __m256 d1 = _mm256_div_ps(_mm256_add_ps(bs_log8(ratio), drift), vt);
    const __m256 d2 = _mm256_sub_ps(d1, vt);
    const __m256 disc = bs_exp8(_mm256_mul_ps(_mm256_sub_ps(_mm256_setzero_ps(), r), T));
    const __m256 value = _mm256_sub_ps(_mm256_mul_ps(S, bs_cnd8(d1)),
                                       _mm256_mul_ps(_mm256_mul_ps(X, disc), bs_cnd8(d2)));
    bs_store_checked(Sa, Xa, Ta, ra, va, result, offset, S, X, T, r, v, d1, d2, value);
}

// Stage four independent SIMD blocks to expose instruction-level parallelism
// while retaining Gm3's vector log/exp approximations and scalar safeguards.
static inline void black_scholes_avx2_four(float Sa[], float Xa[], float Ta[], float ra[], float va[],
                                           float result[], int offset) {
    __m256 S[4], X[4], T[4], r[4], v[4];
    __m256 ratio[4], root_t[4], vt[4], drift[4], d1[4], d2[4], disc[4], value[4];

    for (int block = 0; block < 4; ++block) {
        const int i = offset + block * 8;
        S[block] = _mm256_loadu_ps(Sa + i);
        X[block] = _mm256_loadu_ps(Xa + i);
        T[block] = _mm256_loadu_ps(Ta + i);
        r[block] = _mm256_loadu_ps(ra + i);
        v[block] = _mm256_loadu_ps(va + i);
    }

    for (int block = 0; block < 4; ++block)
        ratio[block] = _mm256_div_ps(S[block], X[block]);
    for (int block = 0; block < 4; ++block) {
        root_t[block] = _mm256_sqrt_ps(T[block]);
        vt[block] = _mm256_mul_ps(v[block], root_t[block]);
        drift[block] = _mm256_mul_ps(
            _mm256_add_ps(r[block],
                          _mm256_mul_ps(_mm256_mul_ps(v[block], v[block]), _mm256_set1_ps(0.5f))),
            T[block]);
    }
    for (int block = 0; block < 4; ++block)
        d1[block] = _mm256_div_ps(_mm256_add_ps(bs_log8(ratio[block]), drift[block]), vt[block]);
    for (int block = 0; block < 4; ++block) {
        d2[block] = _mm256_sub_ps(d1[block], vt[block]);
        disc[block] = bs_exp8(_mm256_mul_ps(_mm256_sub_ps(_mm256_setzero_ps(), r[block]), T[block]));
    }
    for (int block = 0; block < 4; ++block)
        value[block] = _mm256_sub_ps(
            _mm256_mul_ps(S[block], bs_cnd8(d1[block])),
            _mm256_mul_ps(_mm256_mul_ps(X[block], disc[block]), bs_cnd8(d2[block])));

    for (int block = 0; block < 4; ++block)
        bs_store_checked(Sa, Xa, Ta, ra, va, result, offset + block * 8,
                         S[block], X[block], T[block], r[block], v[block],
                         d1[block], d2[block], value[block]);
}

static void black_scholes_avx2(float Sa[], float Xa[], float Ta[], float ra[], float va[], float result[], int count) {
    int i = 0;
    for (; count - i >= 32; i += 32)
        black_scholes_avx2_four(Sa, Xa, Ta, ra, va, result, i);
    for (; count - i >= 8; i += 8)
        black_scholes_avx2_one(Sa, Xa, Ta, ra, va, result, i);
    black_scholes_scalar_range(Sa, Xa, Ta, ra, va, result, i, count);
}
#endif

void black_scholes_serial(float Sa[], float Xa[], float Ta[], float ra[], float va[], float result[], int count) {
#if defined(__AVX2__)
    black_scholes_avx2(Sa, Xa, Ta, ra, va, result, count);
#else
    black_scholes_scalar_range(Sa, Xa, Ta, ra, va, result, 0, count);
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
    const std::size_t stride = static_cast<std::size_t>(n);

    if (threads <= 1 || n / threads < 64) {
        black_scholes_serial(a, a + stride, a + 2 * stride, a + 3 * stride, a + 4 * stride, result, n);
        return;
    }

#pragma omp parallel num_threads(threads)
    {
        const int team_size = omp_get_num_threads();
        const int team_id = omp_get_thread_num();
        const int quotient = n / team_size;
        const int remainder = n % team_size;
        const int begin = team_id * quotient + (team_id < remainder ? team_id : remainder);
        const int end = begin + quotient + (team_id < remainder ? 1 : 0);
        const std::size_t offset = static_cast<std::size_t>(begin);

        black_scholes_serial(a + offset,
                             a + stride + offset,
                             a + 2 * stride + offset,
                             a + 3 * stride + offset,
                             a + 4 * stride + offset,
                             result + offset,
                             end - begin);
    }
}
