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
#include <math.h>

#if defined(__GNUC__) || defined(__clang__)
#if defined(__SSE__)
#include <xmmintrin.h>
#endif
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

#if defined(__GNUC__) || defined(__clang__)
typedef float Float4 __attribute__((vector_size(16)));
#define HAVE_FLOAT4_KERNEL 1

// Approximate ln(x) with the atanh series only on [0.5, 2].
// Arguments outside that bounded interval use the scalar libm result.
static inline Float4 logf4(Float4 x) {
    bool approximate[4];
    Float4 safe;
    for (int lane = 0; lane < 4; ++lane) {
        approximate[lane] = x[lane] >= 0.5f && x[lane] <= 2.f;
        safe[lane] = approximate[lane] ? x[lane] : 1.f;
    }

    const Float4 one = {1.f, 1.f, 1.f, 1.f};
    const Float4 z = (safe - one) / (safe + one);
    const Float4 z2 = z * z;
    Float4 p = {1.f / 13.f, 1.f / 13.f, 1.f / 13.f, 1.f / 13.f};
    p = (1.f / 11.f) + z2 * p;
    p = (1.f / 9.f) + z2 * p;
    p = (1.f / 7.f) + z2 * p;
    p = (1.f / 5.f) + z2 * p;
    p = (1.f / 3.f) + z2 * p;
    p = one + z2 * p;
    const Float4 approx = 2.f * z * p;

    Float4 result;
    for (int lane = 0; lane < 4; ++lane)
        result[lane] = approximate[lane] ? approx[lane] : logf(x[lane]);
    return result;
}

// Degree-9 Taylor polynomial after range reduction on [-4, 4]; use scalar
// expf outside this interval, including non-finite arguments.
static inline Float4 expf4(Float4 x) {
    bool approximate[4];
    Float4 safe;
    for (int lane = 0; lane < 4; ++lane) {
        approximate[lane] = x[lane] >= -4.f && x[lane] <= 4.f;
        safe[lane] = approximate[lane] ? x[lane] * 0.125f : 0.f;
    }

    Float4 p = {1.f / 362880.f, 1.f / 362880.f, 1.f / 362880.f, 1.f / 362880.f};
    p = (1.f / 40320.f) + safe * p;
    p = (1.f / 5040.f) + safe * p;
    p = (1.f / 720.f) + safe * p;
    p = (1.f / 120.f) + safe * p;
    p = (1.f / 24.f) + safe * p;
    p = (1.f / 6.f) + safe * p;
    p = 0.5f + safe * p;
    p = 1.f + safe * p;
    p = 1.f + safe * p;
    const Float4 p2 = p * p;
    const Float4 p4 = p2 * p2;
    const Float4 p8 = p4 * p4;

    Float4 result;
    for (int lane = 0; lane < 4; ++lane)
        result[lane] = approximate[lane] ? p8[lane] : expf(x[lane]);
    return result;
}

// CND's exponential argument is nonpositive. Use a shorter polynomial on
// [-4, 0] and retain scalar libm handling outside that interval.
static inline Float4 expf4_cnd(Float4 x) {
    bool approximate[4];
    Float4 safe;
    for (int lane = 0; lane < 4; ++lane) {
        approximate[lane] = x[lane] >= -4.f && x[lane] <= 0.f;
        safe[lane] = approximate[lane] ? x[lane] * 0.125f : 0.f;
    }

    Float4 p = {1.f / 5040.f, 1.f / 5040.f, 1.f / 5040.f, 1.f / 5040.f};
    p = (1.f / 720.f) + safe * p;
    p = (1.f / 120.f) + safe * p;
    p = (1.f / 24.f) + safe * p;
    p = (1.f / 6.f) + safe * p;
    p = 0.5f + safe * p;
    p = 1.f + safe * p;
    p = 1.f + safe * p;
    const Float4 p2 = p * p;
    const Float4 p4 = p2 * p2;
    const Float4 p8 = p4 * p4;

    Float4 result;
    for (int lane = 0; lane < 4; ++lane)
        result[lane] = approximate[lane] ? p8[lane] : expf(x[lane]);
    return result;
}

// Use the exact hardware square-root operation where SSE is available;
// preserve scalar libm handling for exceptional arguments and other targets.
static inline Float4 sqrtf4(Float4 x) {
    Float4 result;
#if defined(__SSE__)
    const __m128 input = _mm_setr_ps(x[0], x[1], x[2], x[3]);
    float roots[4];
    _mm_storeu_ps(roots, _mm_sqrt_ps(input));
    for (int lane = 0; lane < 4; ++lane) {
        result[lane] = (x[lane] >= 0.f && std::isfinite(x[lane]))
                           ? roots[lane]
                           : sqrtf(x[lane]);
    }
#else
    for (int lane = 0; lane < 4; ++lane)
        result[lane] = sqrtf(x[lane]);
#endif
    return result;
}

// Vectorize CND polynomial and price arithmetic, including bounded expf.
static inline void CND4(const Float4 x, float result[4]) {
    const Float4 one = {1.f, 1.f, 1.f, 1.f};
    const Float4 c2316419 = {0.2316419f, 0.2316419f, 0.2316419f, 0.2316419f};
    const Float4 c031938153 = {0.31938153f, 0.31938153f, 0.31938153f, 0.31938153f};
    const Float4 c0356563782 = {0.356563782f, 0.356563782f, 0.356563782f, 0.356563782f};
    const Float4 c1781477937 = {1.781477937f, 1.781477937f, 1.781477937f, 1.781477937f};
    const Float4 c1821255978 = {-1.821255978f, -1.821255978f, -1.821255978f, -1.821255978f};
    const Float4 c1330274429 = {1.330274429f, 1.330274429f, 1.330274429f, 1.330274429f};
    const Float4 L = {fabsf(x[0]), fabsf(x[1]), fabsf(x[2]), fabsf(x[3])};

    const Float4 k = one / (one + c2316419 * L);
    const Float4 k2 = k * k;
    const Float4 k3 = k2 * k;
    const Float4 k4 = k2 * k2;
    const Float4 k5 = k3 * k2;
    const Float4 polynomial = c031938153 * k - c0356563782 * k2 +
                              c1781477937 * k3 + c1821255978 * k4 +
                              c1330274429 * k5;
    const Float4 exponent = (L * L) * -0.5f;
    const Float4 expValue = expf4_cnd(exponent);
    const Float4 scale = {0.39894228040f * expValue[0],
                          0.39894228040f * expValue[1],
                          0.39894228040f * expValue[2],
                          0.39894228040f * expValue[3]};
    const Float4 w = polynomial * scale;

    for (int lane = 0; lane < 4; ++lane)
        result[lane] = x[lane] > 0.f ? 1.f - w[lane] : w[lane];
}

static inline void black_scholes_four(float Sa[], float Xa[], float Ta[],
                                      float ra[], float va[], float result[],
                                      int i) {
    const Float4 s4 = {Sa[i], Sa[i + 1], Sa[i + 2], Sa[i + 3]};
    const Float4 x4 = {Xa[i], Xa[i + 1], Xa[i + 2], Xa[i + 3]};
    const Float4 t4 = {Ta[i], Ta[i + 1], Ta[i + 2], Ta[i + 3]};
    const Float4 r4 = {ra[i], ra[i + 1], ra[i + 2], ra[i + 3]};
    const Float4 v4 = {va[i], va[i + 1], va[i + 2], va[i + 3]};

    const Float4 logRatio = logf4(s4 / x4);
    const Float4 sqrtT = sqrtf4(t4);
    const Float4 volSqrtT = v4 * sqrtT;
    const Float4 d1 = (logRatio + (r4 + v4 * v4 * 0.5f) * t4) / volSqrtT;
    const Float4 d2 = d1 - volSqrtT;
    const Float4 discount = expf4((-r4) * t4);

    float cnd1[4], cnd2[4];
    CND4(d1, cnd1);
    CND4(d2, cnd2);

    const Float4 cnd14 = {cnd1[0], cnd1[1], cnd1[2], cnd1[3]};
    const Float4 cnd24 = {cnd2[0], cnd2[1], cnd2[2], cnd2[3]};
    const Float4 prices = s4 * cnd14 - x4 * discount * cnd24;

    for (int lane = 0; lane < 4; ++lane)
        result[i + lane] = prices[lane];
}
#endif

#include <omp.h>

extern "C" void run(const void* input1, const void* input2, void* output,
                    int n, int parameter, int threads) {
    if (n <= 0)
        return;

    float *a = (float*)input1;
    float *s = a;
    float *x = s + n;
    float *t = x + n;
    float *r = t + n;
    float *v = r + n;
    float *result = (float*)output;

    const int requested_threads = std::min(threads, n);
#if defined(HAVE_FLOAT4_KERNEL)
    const int vector_groups = n / 4;
    const int vector_threads = std::min(requested_threads, vector_groups);
    // Avoid OpenMP setup unless there are at least 16 vector groups per worker.
    if (requested_threads <= 1 ||
        static_cast<long long>(vector_groups) < 16LL * vector_threads) {
        int i = 0;
        for (; n - i >= 4; i += 4)
            black_scholes_four(s, x, t, r, v, result, i);
        black_scholes_serial(s + i, x + i, t + i, r + i, v + i, result + i, n - i);
        return;
    }

    #pragma omp parallel num_threads(vector_threads)
    {
        const int tid = omp_get_thread_num();
        const int team_size = omp_get_num_threads();
        const int begin_group = static_cast<int>((static_cast<long long>(vector_groups) * tid) / team_size);
        const int end_group = static_cast<int>((static_cast<long long>(vector_groups) * (tid + 1)) / team_size);
        for (int group = begin_group; group < end_group; ++group)
            black_scholes_four(s, x, t, r, v, result, group * 4);
    }

    const int tail = vector_groups * 4;
    if (tail < n)
        black_scholes_serial(s + tail, x + tail, t + tail, r + tail, v + tail, result + tail, n - tail);
#else
    if (requested_threads <= 1) {
        black_scholes_serial(s, x, t, r, v, result, n);
        return;
    }

    #pragma omp parallel num_threads(requested_threads)
    {
        const int tid = omp_get_thread_num();
        const int team_size = omp_get_num_threads();
        const int begin = static_cast<int>((static_cast<long long>(n) * tid) / team_size);
        const int end = static_cast<int>((static_cast<long long>(n) * (tid + 1)) / team_size);
        black_scholes_serial(s + begin, x + begin, t + begin, r + begin, v + begin, result + begin, end - begin);
    }
#endif
}
