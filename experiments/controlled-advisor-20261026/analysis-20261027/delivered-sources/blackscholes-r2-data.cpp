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
#include <cstring>
#include <math.h>
#include <omp.h>

// Cumulative normal distribution function
#if defined(_OPENMP) && _OPENMP >= 201307
#pragma omp declare simd
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

    if (X > 0.f)
        w = 1.f - w;
    return w;
}

#if (defined(__GNUC__) || defined(__clang__)) && (defined(__SSE__) || defined(__ARM_NEON) || defined(__aarch64__))
typedef float Float8 __attribute__((vector_size(32)));

// Prepare the vector CND polynomial; fabsf and expf remain scalar per lane.
static inline void CND8_prepare(const Float8& x, float x_lanes[8],
                                float abs_lanes[8], Float8& polynomial) {
    float abs_values[8];
    std::memcpy(x_lanes, &x, sizeof(x));
    for (int lane = 0; lane < 8; ++lane)
        abs_values[lane] = fabsf(x_lanes[lane]);

    Float8 abs_x;
    std::memcpy(&abs_x, abs_values, sizeof(abs_x));
    std::memcpy(abs_lanes, abs_values, sizeof(abs_values));
    const Float8 one = {1.f, 1.f, 1.f, 1.f, 1.f, 1.f, 1.f, 1.f};

    Float8 k = one / (one + 0.2316419f * abs_x);
    polynomial = k * (0.31938153f + k * (-0.356563782f +
                 k * (1.781477937f + k * (-1.821255978f +
                 k * 1.330274429f))));
}

static inline void CND8_finish(const float x_lanes[8],
                               const float abs_lanes[8],
                               const Float8& polynomial,
                               const float exponential_lanes[8],
                               Float8& result) {
    Float8 exponential;
    std::memcpy(&exponential, exponential_lanes, sizeof(exponential));
    Float8 w = polynomial * (0.39894228040f * exponential);

    float result_lanes[8];
    std::memcpy(result_lanes, &w, sizeof(w));
    for (int lane = 0; lane < 8; ++lane) {
        if (x_lanes[lane] > 0.f)
            result_lanes[lane] = 1.f - result_lanes[lane];
    }
    std::memcpy(&result, result_lanes, sizeof(result));
}

static inline Float8 CND8(const Float8& x) {
    float x_lanes[8], abs_lanes[8], exponential_lanes[8];
    Float8 polynomial, result;
    CND8_prepare(x, x_lanes, abs_lanes, polynomial);
    for (int lane = 0; lane < 8; ++lane)
        exponential_lanes[lane] = expf(-abs_lanes[lane] * abs_lanes[lane] * .5f);
    CND8_finish(x_lanes, abs_lanes, polynomial, exponential_lanes, result);
    return result;
}

// Interleave scalar expf calls for four CND vectors from two independent blocks.
static inline void CND8Four(const Float8& x0, const Float8& x1,
                            const Float8& x2, const Float8& x3,
                            Float8& result0, Float8& result1,
                            Float8& result2, Float8& result3) {
    float x_lanes[4][8], abs_lanes[4][8], exponential_lanes[4][8];
    Float8 polynomial[4];
    CND8_prepare(x0, x_lanes[0], abs_lanes[0], polynomial[0]);
    CND8_prepare(x1, x_lanes[1], abs_lanes[1], polynomial[1]);
    CND8_prepare(x2, x_lanes[2], abs_lanes[2], polynomial[2]);
    CND8_prepare(x3, x_lanes[3], abs_lanes[3], polynomial[3]);

    for (int lane = 0; lane < 8; ++lane) {
        for (int vector = 0; vector < 4; ++vector)
            exponential_lanes[vector][lane] = expf(-abs_lanes[vector][lane] *
                                                    abs_lanes[vector][lane] * .5f);
    }

    CND8_finish(x_lanes[0], abs_lanes[0], polynomial[0], exponential_lanes[0], result0);
    CND8_finish(x_lanes[1], abs_lanes[1], polynomial[1], exponential_lanes[1], result1);
    CND8_finish(x_lanes[2], abs_lanes[2], polynomial[2], exponential_lanes[2], result2);
    CND8_finish(x_lanes[3], abs_lanes[3], polynomial[3], exponential_lanes[3], result3);
}

// One unaligned-safe eight-lane Black-Scholes block. Transcendentals are scalar.
static inline void black_scholes_simd8(const float Sa[], const float Xa[],
                                       const float Ta[], const float ra[],
                                       const float va[], float result[], int i) {
    Float8 s, x, t, r, v;
    std::memcpy(&s, Sa + i, sizeof(s));
    std::memcpy(&x, Xa + i, sizeof(x));
    std::memcpy(&t, Ta + i, sizeof(t));
    std::memcpy(&r, ra + i, sizeof(r));
    std::memcpy(&v, va + i, sizeof(v));

    float s_lanes[8], x_lanes[8], t_lanes[8], r_lanes[8], v_lanes[8];
    std::memcpy(s_lanes, &s, sizeof(s));
    std::memcpy(x_lanes, &x, sizeof(x));
    std::memcpy(t_lanes, &t, sizeof(t));
    std::memcpy(r_lanes, &r, sizeof(r));
    std::memcpy(v_lanes, &v, sizeof(v));

    float log_lanes[8], sqrt_lanes[8], discount_lanes[8];
    for (int lane = 0; lane < 8; ++lane) {
        log_lanes[lane] = logf(s_lanes[lane] / x_lanes[lane]);
        sqrt_lanes[lane] = sqrtf(t_lanes[lane]);
        discount_lanes[lane] = expf(-r_lanes[lane] * t_lanes[lane]);
    }

    Float8 log_ratio, sqrt_t, discount;
    std::memcpy(&log_ratio, log_lanes, sizeof(log_ratio));
    std::memcpy(&sqrt_t, sqrt_lanes, sizeof(sqrt_t));
    std::memcpy(&discount, discount_lanes, sizeof(discount));

    Float8 vol_sqrt_t = v * sqrt_t;
    Float8 d1 = (log_ratio + (r + v * v * .5f) * t) / vol_sqrt_t;
    Float8 d2 = d1 - vol_sqrt_t;
    Float8 value = s * CND8(d1) - x * discount * CND8(d2);
    std::memcpy(result + i, &value, sizeof(value));
}

// Fused pair of eight-lane blocks, interleaving independent scalar calls.
static inline void black_scholes_simd8_pair(const float Sa[], const float Xa[],
                                            const float Ta[], const float ra[],
                                            const float va[], float result[], int i) {
    Float8 s0, x0, t0, r0, v0, s1, x1, t1, r1, v1;
    std::memcpy(&s0, Sa + i, sizeof(s0));
    std::memcpy(&x0, Xa + i, sizeof(x0));
    std::memcpy(&t0, Ta + i, sizeof(t0));
    std::memcpy(&r0, ra + i, sizeof(r0));
    std::memcpy(&v0, va + i, sizeof(v0));
    std::memcpy(&s1, Sa + i + 8, sizeof(s1));
    std::memcpy(&x1, Xa + i + 8, sizeof(x1));
    std::memcpy(&t1, Ta + i + 8, sizeof(t1));
    std::memcpy(&r1, ra + i + 8, sizeof(r1));
    std::memcpy(&v1, va + i + 8, sizeof(v1));

    float s_lanes[2][8], x_lanes[2][8], t_lanes[2][8];
    float r_lanes[2][8], v_lanes[2][8];
    std::memcpy(s_lanes[0], &s0, sizeof(s0));
    std::memcpy(x_lanes[0], &x0, sizeof(x0));
    std::memcpy(t_lanes[0], &t0, sizeof(t0));
    std::memcpy(r_lanes[0], &r0, sizeof(r0));
    std::memcpy(v_lanes[0], &v0, sizeof(v0));
    std::memcpy(s_lanes[1], &s1, sizeof(s1));
    std::memcpy(x_lanes[1], &x1, sizeof(x1));
    std::memcpy(t_lanes[1], &t1, sizeof(t1));
    std::memcpy(r_lanes[1], &r1, sizeof(r1));
    std::memcpy(v_lanes[1], &v1, sizeof(v1));

    float log_lanes[2][8], sqrt_lanes[2][8], discount_lanes[2][8];
    for (int lane = 0; lane < 8; ++lane) {
        log_lanes[0][lane] = logf(s_lanes[0][lane] / x_lanes[0][lane]);
        log_lanes[1][lane] = logf(s_lanes[1][lane] / x_lanes[1][lane]);
    }
    for (int lane = 0; lane < 8; ++lane) {
        sqrt_lanes[0][lane] = sqrtf(t_lanes[0][lane]);
        sqrt_lanes[1][lane] = sqrtf(t_lanes[1][lane]);
    }
    for (int lane = 0; lane < 8; ++lane) {
        discount_lanes[0][lane] = expf(-r_lanes[0][lane] * t_lanes[0][lane]);
        discount_lanes[1][lane] = expf(-r_lanes[1][lane] * t_lanes[1][lane]);
    }

    Float8 log0, sqrt0, discount0, log1, sqrt1, discount1;
    std::memcpy(&log0, log_lanes[0], sizeof(log0));
    std::memcpy(&sqrt0, sqrt_lanes[0], sizeof(sqrt0));
    std::memcpy(&discount0, discount_lanes[0], sizeof(discount0));
    std::memcpy(&log1, log_lanes[1], sizeof(log1));
    std::memcpy(&sqrt1, sqrt_lanes[1], sizeof(sqrt1));
    std::memcpy(&discount1, discount_lanes[1], sizeof(discount1));

    Float8 vol_sqrt0 = v0 * sqrt0;
    Float8 d10 = (log0 + (r0 + v0 * v0 * .5f) * t0) / vol_sqrt0;
    Float8 d20 = d10 - vol_sqrt0;
    Float8 vol_sqrt1 = v1 * sqrt1;
    Float8 d11 = (log1 + (r1 + v1 * v1 * .5f) * t1) / vol_sqrt1;
    Float8 d21 = d11 - vol_sqrt1;

    Float8 cnd10, cnd20, cnd11, cnd21;
    CND8Four(d10, d20, d11, d21, cnd10, cnd20, cnd11, cnd21);
    Float8 value0 = s0 * cnd10 - x0 * discount0 * cnd20;
    Float8 value1 = s1 * cnd11 - x1 * discount1 * cnd21;
    std::memcpy(result + i, &value0, sizeof(value0));
    std::memcpy(result + i + 8, &value1, sizeof(value1));
}
#endif

static inline void black_scholes_one(const float Sa[], const float Xa[],
                                     const float Ta[], const float ra[],
                                     const float va[], float result[], int i) {
    float S = Sa[i], X = Xa[i];
    float T = Ta[i], r = ra[i];
    float v = va[i];

    float d1 = (logf(S / X) + (r + v * v * .5f) * T) / (v * sqrtf(T));
    float d2 = d1 - v * sqrtf(T);

    result[i] = S * CND(d1) - X * expf(-r * T) * CND(d2);
}

void black_scholes_serial(float Sa[], float Xa[], float Ta[], float ra[], float va[], float result[], int count) {
    int i = 0;
#if (defined(__GNUC__) || defined(__clang__)) && (defined(__SSE__) || defined(__ARM_NEON) || defined(__aarch64__))
    for (; count - i >= 16; i += 16)
        black_scholes_simd8_pair(Sa, Xa, Ta, ra, va, result, i);
    if (count - i >= 8) {
        black_scholes_simd8(Sa, Xa, Ta, ra, va, result, i);
        i += 8;
    }
#endif
    for (; i < count; ++i)
        black_scholes_one(Sa, Xa, Ta, ra, va, result, i);
}

static void black_scholes_parallel_static(const float Sa[], const float Xa[],
                                          const float Ta[], const float ra[],
                                          const float va[], float result[],
                                          int count, int threads) {
    if (count <= 0)
        return;
#if (defined(__GNUC__) || defined(__clang__)) && (defined(__SSE__) || defined(__ARM_NEON) || defined(__aarch64__))
    const int pair_count = count / 16;
    const int single_block_count = (count % 16) / 8;
    const int work_units = pair_count + single_block_count;
#pragma omp parallel for schedule(static) num_threads(threads)
    for (int unit = 0; unit < work_units; ++unit) {
        if (unit < pair_count) {
            black_scholes_simd8_pair(Sa, Xa, Ta, ra, va, result, unit * 16);
        } else {
            black_scholes_simd8(Sa, Xa, Ta, ra, va, result, pair_count * 16);
        }
    }
    const int vectorized_count = pair_count * 16 + single_block_count * 8;
    for (int i = vectorized_count; i < count; ++i)
        black_scholes_one(Sa, Xa, Ta, ra, va, result, i);
#else
#pragma omp parallel for schedule(static) num_threads(threads)
    for (int i = 0; i < count; ++i)
        black_scholes_one(Sa, Xa, Ta, ra, va, result, i);
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
    const float* a = static_cast<const float*>(input1);
    if (threads <= 1) {
        black_scholes_serial(const_cast<float*>(a), const_cast<float*>(a + n),
                             const_cast<float*>(a + 2 * n), const_cast<float*>(a + 3 * n),
                             const_cast<float*>(a + 4 * n), static_cast<float*>(output), n);
        return;
    }
    black_scholes_parallel_static(a, a + n, a + 2 * n, a + 3 * n, a + 4 * n,
                                  static_cast<float*>(output), n, threads);
}
