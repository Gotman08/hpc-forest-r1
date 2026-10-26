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
#include <cstdint>
#include <cstring>
#include <math.h>
#include <omp.h>

// Cumulative normal distribution function
static inline float CND(float X) {
    const float invSqrt2Pi = 0.39894228040f;
    const float L = fabsf(X);

    // Signed [2/2] Padé approximation in the central region.
    if (L < 1.25f) {
        const float x2 = X * X;
        const float numerator = 1.f + x2 * (0.0363247863247863f + 0.0037596662601758f * x2);
        const float denominator = 1.f + x2 * (0.202991452991453f + 0.0125915750915751f * x2);
        return 0.5f + invSqrt2Pi * (X * (numerator / denominator));
    }

    // Keep the exponential tail, evaluating its polynomial in Horner form.
    float k = 1.f / (1.f + 0.2316419f * L);
    float w = k * (0.31938153f + k * (-0.356563782f + k * (1.781477937f + k * (-1.821255978f + k * 1.330274429f))));
    w *= invSqrt2Pi * expf(-L * L * .5f);

    if (X > 0.f)
        w = 1.f - w;
    return w;
}

static inline float black_scholes_value(float S, float X, float T, float r, float v) {
    float d1 = (logf(S / X) + (r + v * v * .5f) * T) / (v * sqrtf(T));
    float d2 = d1 - v * sqrtf(T);

    return S * CND(d1) - X * expf(-r * T) * CND(d2);
}

void black_scholes_serial(float Sa[], float Xa[], float Ta[], float ra[], float va[], float result[], int count, int threads) {
    const int work_limited_threads = count / 8192;
    const int team_size = std::min(threads, work_limited_threads);

    if (team_size > 1) {
#pragma omp parallel num_threads(team_size)
        {
            const int worker = omp_get_thread_num();
            const int workers = omp_get_num_threads();
            const int chunk = count / workers;
            const int remainder = count % workers;
            const int begin = worker * chunk + std::min(worker, remainder);
            const int end = begin + chunk + (worker < remainder ? 1 : 0);

            for (int i = begin; i < end; ++i) {
                float S = Sa[i], X = Xa[i];
                float T = Ta[i], r = ra[i];
                float v = va[i];

                result[i] = black_scholes_value(S, X, T, r, v);
            }
        }
    } else {
        for (int i = 0; i < count; ++i) {
            float S = Sa[i], X = Xa[i];
            float T = Ta[i], r = ra[i];
            float v = va[i];

            result[i] = black_scholes_value(S, X, T, r, v);
        }
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

extern "C" void run(const void* input1, const void* input2, void* output, int n, int parameter, int threads) {
    float* a = (float*)input1;
    black_scholes_serial(a, a + n, a + 2 * n, a + 3 * n, a + 4 * n, (float*)output, n, threads);
}
