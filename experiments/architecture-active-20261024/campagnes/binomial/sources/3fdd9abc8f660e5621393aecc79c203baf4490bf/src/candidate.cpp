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

static const int BINOMIAL_SIMD_LANES = 8;

static inline void binomial_put_batch(float Sa[], float Xa[], float Ta[], float ra[], float va[], float result[], int count, int batch) {
    const int base = batch * BINOMIAL_SIMD_LANES;
    const int active = std::min<int>(BINOMIAL_SIMD_LANES, count - base);
    float V[BINOMIAL_NUM][BINOMIAL_SIMD_LANES];
    float S[BINOMIAL_SIMD_LANES], X[BINOMIAL_SIMD_LANES];
    float downWeight[BINOMIAL_SIMD_LANES], upWeight[BINOMIAL_SIMD_LANES];
    double powerStep[BINOMIAL_SIMD_LANES];
    double inversePowerStep[BINOMIAL_SIMD_LANES];
    double positiveUpow[BINOMIAL_SIMD_LANES];
    double negativeUpow[BINOMIAL_SIMD_LANES];

    // Pack independent options into contiguous SIMD lanes and precompute weights.
    #pragma omp simd
    for (int lane = 0; lane < active; ++lane) {
        const int i = base + lane;
        S[lane] = Sa[i];
        X[lane] = Xa[i];
        const float T = Ta[i], r = ra[i], v = va[i];

        const float dt = T / BINOMIAL_NUM;
        const float u = expf(v * sqrtf(dt));
        const float d = 1.f / u;
        const float disc = expf(r * dt);
        const float invDiscountedSpan = 1.f / (disc * (u - d));
        downWeight[lane] = (u - disc) * invDiscountedSpan;
        upWeight[lane] = (disc - d) * invDiscountedSpan;

        powerStep[lane] = static_cast<double>(u) * static_cast<double>(u);
        inversePowerStep[lane] = 1.0 / powerStep[lane];
        positiveUpow[lane] = 1.0;
        negativeUpow[lane] = 1.0;
    }

    // Exponents are 2*j-64: initialize j=32 (exponent zero), then recur on both sides.
    const int powerCenter = BINOMIAL_NUM / 2;
    #pragma omp simd
    for (int lane = 0; lane < active; ++lane)
        V[powerCenter][lane] = std::max(0.f, X[lane] - S[lane]);

    // Advance the positive and negative power sequences together; each sequence
    // retains its original multiplication order and covers its original indices.
    for (int offset = 1; offset < powerCenter; ++offset) {
        const int upperJ = powerCenter + offset;
        const int lowerJ = powerCenter - offset;
        #pragma omp simd
        for (int lane = 0; lane < active; ++lane) {
            positiveUpow[lane] *= powerStep[lane];
            negativeUpow[lane] *= inversePowerStep[lane];
            V[upperJ][lane] = std::max(0.f, X[lane] - S[lane] * static_cast<float>(positiveUpow[lane]));
            V[lowerJ][lane] = std::max(0.f, X[lane] - S[lane] * static_cast<float>(negativeUpow[lane]));
        }
    }

    // Finish the negative sequence at exponent -64 (j=0).
    #pragma omp simd
    for (int lane = 0; lane < active; ++lane) {
        negativeUpow[lane] *= inversePowerStep[lane];
        V[0][lane] = std::max(0.f, X[lane] - S[lane] * static_cast<float>(negativeUpow[lane]));
    }

    // Keep the backward j and forward k traversal, with discounted weights hoisted.
    for (int j = BINOMIAL_NUM - 1; j >= 0; --j) {
        for (int k = 0; k < j; ++k) {
            #pragma omp simd
            for (int lane = 0; lane < active; ++lane)
                V[k][lane] = downWeight[lane] * V[k][lane] + upWeight[lane] * V[k + 1][lane];
        }
    }

    #pragma omp simd
    for (int lane = 0; lane < active; ++lane)
        result[base + lane] = V[0][lane];
}

static const int BINOMIAL_MIN_ITEMS_PER_THREAD = 256;

void binomial_put_dispatch(float Sa[], float Xa[], float Ta[], float ra[], float va[], float result[], int count, int threads) {
    if (count <= 0)
        return;

    const int batch_count = count / BINOMIAL_SIMD_LANES + (count % BINOMIAL_SIMD_LANES != 0);
    // Keep small calls serial and cap workers so each parallel worker has useful work.
    const int worker_count = std::min(threads, count / BINOMIAL_MIN_ITEMS_PER_THREAD);
    if (worker_count <= 1) {
        for (int batch = 0; batch < batch_count; ++batch)
            binomial_put_batch(Sa, Xa, Ta, ra, va, result, count, batch);
        return;
    }

    // Parallelize independent batches; each batch vectorizes across its active lanes.
    #pragma omp parallel for schedule(static) num_threads(worker_count)
    for (int batch = 0; batch < batch_count; ++batch)
        binomial_put_batch(Sa, Xa, Ta, ra, va, result, count, batch);
}

extern "C" void run(const void* input1,const void* input2,void* output,int n,int parameter,int threads)
{
    float* a = (float*)input1;
    binomial_put_dispatch(a, a + n, a + 2 * n, a + 3 * n, a + 4 * n, (float*)output, n, threads);
}
