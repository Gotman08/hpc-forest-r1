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
#include <omp.h>

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

static inline void binomial_put_one(float S, float X, float T, float r, float v, float& result) {
    float V[BINOMIAL_NUM];

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

    result = V[0];
}

void binomial_put_serial(float Sa[], float Xa[], float Ta[], float ra[], float va[], float result[], int count) {
    for (int i = 0; i < count; ++i)
        binomial_put_one(Sa[i], Xa[i], Ta[i], ra[i], va[i], result[i]);
}

static void binomial_put_dispatch(float Sa[], float Xa[], float Ta[], float ra[], float va[], float result[], int count, int threads) {
    if (count <= 0)
        return;

    // Keep small calls serial; for larger calls, target at least 64 elements
    // per requested worker while respecting the caller's thread budget.
    const int min_elements_per_worker = 64;
    if (threads <= 1 || count < 2 * min_elements_per_worker) {
        binomial_put_serial(Sa, Xa, Ta, ra, va, result, count);
        return;
    }

    const int worker_count = std::min(threads, count / min_elements_per_worker);
    if (worker_count <= 1) {
        binomial_put_serial(Sa, Xa, Ta, ra, va, result, count);
        return;
    }

    // Static worksharing assigns every output index exactly once. If the
    // runtime forms a smaller team, the loop still covers the full range.
    #pragma omp parallel for num_threads(worker_count) schedule(static)
    for (int i = 0; i < count; ++i)
        binomial_put_one(Sa[i], Xa[i], Ta[i], ra[i], va[i], result[i]);
}

extern "C" void run(const void* input1, const void* input2, void* output, int n, int parameter, int threads) {
    if (n <= 0)
        return;

    float* a = (float*)input1;
    binomial_put_dispatch(a, a + n, a + 2 * n, a + 3 * n, a + 4 * n, (float*)output, n, threads);
}
