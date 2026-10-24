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

static inline double integer_power(double base, int exponent) {
    double result = 1.0;
    while (exponent > 0) {
        if (exponent & 1)
            result *= base;
        base *= base;
        exponent >>= 1;
    }
    return result;
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

void binomial_put_parallel(float Sa[], float Xa[], float Ta[], float ra[], float va[], float result[], int count, int threads) {
    const int worker_count = std::max(1, std::min(threads, count));
    const int transitions = BINOMIAL_NUM - 1;

    #pragma omp parallel num_threads(worker_count) if (worker_count > 1)
    {
        float V[BINOMIAL_NUM];

        #pragma omp for schedule(static)
        for (int i = 0; i < count; ++i) {
            float S = Sa[i], X = Xa[i];
            float T = Ta[i], r = ra[i];
            float v = va[i];

            float dt = T / BINOMIAL_NUM;
            float u = expf(v * sqrtf(dt));
            float d = 1.f / u;
            float disc = expf(r * dt);
            float Pu = (disc - d) / (u - d);
            float Pd = 1.f - Pu;

            float upow = powf(u, static_cast<float>(-BINOMIAL_NUM));
            const float u2 = u * u;
            for (int j = 0; j < BINOMIAL_NUM; ++j) {
                V[j] = std::max(0.f, X - S * upow);
                if (j + 1 < BINOMIAL_NUM)
                    upow *= u2;
            }

            const double pu = static_cast<double>(Pu);
            const double pd = static_cast<double>(Pd);
            double value = 0.0;

            if (pu <= pd) {
                double weight = integer_power(pd, transitions);
                const double ratio = pu / pd;
                for (int j = 0; j <= transitions; ++j) {
                    value += weight * static_cast<double>(V[j]);
                    if (j < transitions) {
                        const double coefficient_ratio =
                            static_cast<double>(transitions - j) / static_cast<double>(j + 1);
                        weight *= coefficient_ratio * ratio;
                    }
                }
            } else {
                double weight = integer_power(pu, transitions);
                const double ratio = pd / pu;
                for (int j = transitions; j >= 0; --j) {
                    value += weight * static_cast<double>(V[j]);
                    if (j > 0) {
                        const double coefficient_ratio =
                            static_cast<double>(j) / static_cast<double>(transitions - j + 1);
                        weight *= coefficient_ratio * ratio;
                    }
                }
            }

            const double discount = integer_power(static_cast<double>(disc), transitions);
            result[i] = static_cast<float>(value / discount);
        }
    }
}

#include <cstdint>
#include <cstring>
#include <cmath>
#include <algorithm>
#include <omp.h>
extern "C" void run(const void* input1, const void* input2, void* output, int n, int parameter, int threads) {
    float* a = (float*)input1;
    binomial_put_parallel(a, a + n, a + 2 * n, a + 3 * n, a + 4 * n, (float*)output, n, threads);
}
