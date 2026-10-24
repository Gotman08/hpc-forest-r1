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
#include <cmath>

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

static inline double power63(double x) {
    const double x2 = x * x;
    const double x4 = x2 * x2;
    const double x8 = x4 * x4;
    const double x16 = x8 * x8;
    const double x32 = x16 * x16;
    return x32 * x16 * x8 * x4 * x2 * x;
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

        // Retain the original recurrence for values outside the probability domain.
        if (!(Pu >= 0.f && Pu <= 1.f) || !(u > 0.f) || !std::isfinite(u)) {
            for (int j = 0; j < BINOMIAL_NUM; ++j) {
                float upow = powf(u, (float)(2 * j - BINOMIAL_NUM));
                V[j] = std::max(0.f, X - S * upow);
            }

            for (int j = BINOMIAL_NUM - 1; j >= 0; --j)
                for (int k = 0; k < j; ++k)
                    V[k] = ((1 - Pu) * V[k] + Pu * V[k + 1]) / disc;

            result[i] = V[0];
            continue;
        }

        // The 64 terminal payoffs correspond to j=0..63 and exponents 2*j-64.
        // Build those powers from u^-64 using the factor u^2; no j=64 payoff is added.
        double upow = std::pow((double)u, -64.0);
        const double uSquared = (double)u * (double)u;
        for (int j = 0; j < BINOMIAL_NUM; ++j) {
            V[j] = std::max(0.f, X - S * (float)upow);
            upow *= uSquared;
        }

        // There are 63 updates, so each terminal payoff receives exactly 63 discounts.
        const double inverseDiscount = 1.0 / (double)disc;
        double discountFactor = 1.0;
        for (int step = 0; step < BINOMIAL_NUM - 1; ++step)
            discountFactor *= inverseDiscount;

        const double probability = (double)Pu;
        double weightedPayoff = 0.0;
        if (probability <= 0.5) {
            const double downProbability = 1.0 - probability;
            const double odds = probability / downProbability;
            double weight = power63(downProbability);
            for (int j = 0; j < BINOMIAL_NUM; ++j) {
                weightedPayoff += weight * (double)V[j];
                if (j + 1 < BINOMIAL_NUM)
                    weight *= ((double)(BINOMIAL_NUM - 1 - j) / (double)(j + 1)) * odds;
            }
        } else {
            const double odds = (1.0 - probability) / probability;
            double weight = power63(probability);
            for (int j = BINOMIAL_NUM - 1; j >= 0; --j) {
                weightedPayoff += weight * (double)V[j];
                if (j > 0)
                    weight *= ((double)j / (double)(BINOMIAL_NUM - j)) * odds;
            }
        }

        result[i] = (float)(weightedPayoff * discountFactor);
    }
}
#include <cstdint>
#include <cstring>
#include <cmath>
#include <algorithm>
#include <omp.h>
extern "C" void run(const void* input1,const void* input2,void* output,int n,int parameter,int threads)
{float*a=(float*)input1;binomial_put_serial(a,a+n,a+2*n,a+3*n,a+4*n,(float*)output,n);}
