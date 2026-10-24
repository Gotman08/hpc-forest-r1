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
    enum { SIMD_LANES = 8 };

    for (int base = 0; base < count;) {
        const int active = std::min(SIMD_LANES, count - base);
        float V[BINOMIAL_NUM][SIMD_LANES];
        float S[SIMD_LANES], X[SIMD_LANES];
        float u[SIMD_LANES], Pu[SIMD_LANES], disc[SIMD_LANES];

        // Pack independent options into contiguous SIMD lanes.
        #pragma omp simd
        for (int lane = 0; lane < active; ++lane) {
            const int i = base + lane;
            S[lane] = Sa[i];
            X[lane] = Xa[i];
            const float T = Ta[i], r = ra[i], v = va[i];

            const float dt = T / BINOMIAL_NUM;
            u[lane] = expf(v * sqrtf(dt));
            const float d = 1.f / u[lane];
            disc[lane] = expf(r * dt);
            Pu[lane] = (disc[lane] - d) / (u[lane] - d);
        }

        // Retain the baseline terminal-power generation for every option.
        for (int j = 0; j < BINOMIAL_NUM; ++j) {
            const float exponent = (float)(2 * j - BINOMIAL_NUM);
            #pragma omp simd
            for (int lane = 0; lane < active; ++lane) {
                const float upow = powf(u[lane], exponent);
                V[j][lane] = std::max(0.f, X[lane] - S[lane] * upow);
            }
        }

        // Keep the baseline rollback order and arithmetic, vectorized across options.
        for (int j = BINOMIAL_NUM - 1; j >= 0; --j) {
            for (int k = 0; k < j; ++k) {
                #pragma omp simd
                for (int lane = 0; lane < active; ++lane)
                    V[k][lane] = ((1 - Pu[lane]) * V[k][lane] + Pu[lane] * V[k + 1][lane]) / disc[lane];
            }
        }

        #pragma omp simd
        for (int lane = 0; lane < active; ++lane)
            result[base + lane] = V[0][lane];

        base += active;
    }
}
#include <cstdint>
#include <cstring>
#include <cmath>
#include <algorithm>
#include <omp.h>
extern "C" void run(const void* input1,const void* input2,void* output,int n,int parameter,int threads)
{float*a=(float*)input1;binomial_put_serial(a,a+n,a+2*n,a+3*n,a+4*n,(float*)output,n);}
