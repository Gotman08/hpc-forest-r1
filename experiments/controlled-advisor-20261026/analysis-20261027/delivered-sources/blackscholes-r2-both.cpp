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
#include <cstring>
#include <math.h>
#include <omp.h>
#if defined(__AVX__)
#include <immintrin.h>
#elif defined(__SSE2__)
#include <emmintrin.h>
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

static inline void black_scholes_element(const float Sa[], const float Xa[],
                                         const float Ta[], const float ra[],
                                         const float va[], float result[], int i) {
    float S = Sa[i], X = Xa[i];
    float T = Ta[i], r = ra[i];
    float v = va[i];

    float d1 = (logf(S / X) + (r + v * v * .5f) * T) / (v * sqrtf(T));
    float d2 = d1 - v * sqrtf(T);

    result[i] = S * CND(d1) - X * expf(-r * T) * CND(d2);
}

#if defined(__GNUC__) || defined(__clang__)
typedef float float4 __attribute__((vector_size(16)));

#if defined(__SSE2__)
// Bounded SSE2 exponential; use expf for groups outside the fast-path range.
static inline float4 exp4(float4 x) {
    bool safe = true;
    for (int lane = 0; lane < 4; ++lane) {
        if (!(x[lane] >= -80.f && x[lane] <= 80.f))
            safe = false;
    }

    if (safe) {
        const __m128 one = _mm_set1_ps(1.f);
        const __m128 half = _mm_set1_ps(0.5f);
        const __m128 minusHalf = _mm_set1_ps(-0.5f);
        const __m128 vx = _mm_loadu_ps(&x[0]);
        const __m128 y = _mm_mul_ps(vx, _mm_set1_ps(1.4426950408889634f));

        // Truncate, then adjust to the nearest integer independently of MXCSR rounding mode.
        const __m128i nTrunc = _mm_cvttps_epi32(y);
        __m128 n = _mm_cvtepi32_ps(nTrunc);
        const __m128 fraction = _mm_sub_ps(y, n);
        const __m128 roundUp = _mm_and_ps(_mm_cmpgt_ps(fraction, half), one);
        const __m128 roundDown = _mm_and_ps(_mm_cmplt_ps(fraction, minusHalf), one);
        n = _mm_add_ps(_mm_sub_ps(n, roundDown), roundUp);

        // Reduce x to approximately [-ln(2)/2, ln(2)/2] using a split ln(2).
        __m128 r = _mm_sub_ps(vx, _mm_mul_ps(n, _mm_set1_ps(0.693359375f)));
        r = _mm_sub_ps(r, _mm_mul_ps(n, _mm_set1_ps(-0.00021219444005469058f)));

        // Degree-seven Taylor approximation on the reduced interval.
        __m128 p = _mm_set1_ps(1.f / 5040.f);
        p = _mm_add_ps(_mm_mul_ps(p, r), _mm_set1_ps(1.f / 720.f));
        p = _mm_add_ps(_mm_mul_ps(p, r), _mm_set1_ps(1.f / 120.f));
        p = _mm_add_ps(_mm_mul_ps(p, r), _mm_set1_ps(1.f / 24.f));
        p = _mm_add_ps(_mm_mul_ps(p, r), _mm_set1_ps(1.f / 6.f));
        p = _mm_add_ps(_mm_mul_ps(p, r), _mm_set1_ps(0.5f));
        p = _mm_add_ps(_mm_mul_ps(p, r), one);
        p = _mm_add_ps(_mm_mul_ps(p, r), one);

        const __m128i exponent = _mm_add_epi32(_mm_cvttps_epi32(n), _mm_set1_epi32(127));
        const __m128 scale = _mm_castsi128_ps(_mm_slli_epi32(exponent, 23));
        const __m128 result = _mm_mul_ps(p, scale);
        float4 out;
        _mm_storeu_ps(&out[0], result);
        return out;
    }

    float4 out;
    for (int lane = 0; lane < 4; ++lane)
        out[lane] = expf(x[lane]);
    return out;
}
#else
static inline float4 exp4(float4 x) {
    float4 out;
    for (int lane = 0; lane < 4; ++lane)
        out[lane] = expf(x[lane]);
    return out;
}
#endif

#if defined(__SSE2__)
// Use hardware SIMD square root when available.
static inline float4 sqrt4(float4 x) {
    float4 out;
    const __m128 vx = _mm_loadu_ps(&x[0]);
    _mm_storeu_ps(&out[0], _mm_sqrt_ps(vx));
    return out;
}
#else
static inline float4 sqrt4(float4 x) {
    float4 out;
    for (int lane = 0; lane < 4; ++lane)
        out[lane] = sqrtf(x[lane]);
    return out;
}
#endif

static inline float4 CND4(float4 x) {
    const float4 one = {1.f, 1.f, 1.f, 1.f};
    const float4 c0 = {0.31938153f, 0.31938153f, 0.31938153f, 0.31938153f};
    const float4 c1 = {0.356563782f, 0.356563782f, 0.356563782f, 0.356563782f};
    const float4 c2 = {1.781477937f, 1.781477937f, 1.781477937f, 1.781477937f};
    const float4 c3 = {-1.821255978f, -1.821255978f, -1.821255978f, -1.821255978f};
    const float4 c4 = {1.330274429f, 1.330274429f, 1.330274429f, 1.330274429f};
    const float4 invSqrt2Pi = {0.39894228040f, 0.39894228040f, 0.39894228040f, 0.39894228040f};
    const float4 coefficient = {0.2316419f, 0.2316419f, 0.2316419f, 0.2316419f};
    const float4 half = {0.5f, 0.5f, 0.5f, 0.5f};

    float4 L;
    for (int lane = 0; lane < 4; ++lane)
        L[lane] = fabsf(x[lane]);

    float4 k = one / (one + coefficient * L);
    float4 polynomial = ((((c4 * k + c3) * k + c2) * k - c1) * k + c0);
    float4 w = polynomial * k;

    float4 densityArg;
    for (int lane = 0; lane < 4; ++lane)
        densityArg[lane] = -L[lane] * L[lane] * half[lane];
    float4 density = exp4(densityArg);
    w *= invSqrt2Pi * density;

    for (int lane = 0; lane < 4; ++lane) {
        if (x[lane] > 0.f)
            w[lane] = 1.f - w[lane];
    }
    return w;
}

static inline void black_scholes_block4(const float Sa[], const float Xa[],
                                        const float Ta[], const float ra[],
                                        const float va[], float result[], int i) {
    float4 S, X, T, r, v;
    std::memcpy(&S, Sa + i, sizeof(S));
    std::memcpy(&X, Xa + i, sizeof(X));
    std::memcpy(&T, Ta + i, sizeof(T));
    std::memcpy(&r, ra + i, sizeof(r));
    std::memcpy(&v, va + i, sizeof(v));

    float4 sqrtT = sqrt4(T);
    float4 d1, d2, discountArg;
    for (int lane = 0; lane < 4; ++lane) {
        d1[lane] = (logf(S[lane] / X[lane]) +
                    (r[lane] + v[lane] * v[lane] * .5f) * T[lane]) /
                   (v[lane] * sqrtT[lane]);
        d2[lane] = d1[lane] - v[lane] * sqrtT[lane];
        discountArg[lane] = -r[lane] * T[lane];
    }
    float4 discountedStrike = exp4(discountArg);

    float4 prices = S * CND4(d1) - X * discountedStrike * CND4(d2);
    std::memcpy(result + i, &prices, sizeof(prices));
}

#if defined(__AVX__)
typedef float float8 __attribute__((vector_size(32)));

static inline float8 exp8(float8 x) {
    float4 low, high;
    std::memcpy(&low, &x, sizeof(low));
    std::memcpy(&high, reinterpret_cast<const char*>(&x) + sizeof(low), sizeof(high));

    low = exp4(low);
    high = exp4(high);

    float8 out;
    std::memcpy(&out, &low, sizeof(low));
    std::memcpy(reinterpret_cast<char*>(&out) + sizeof(low), &high, sizeof(high));
    return out;
}

static inline float8 CND8(float8 x) {
    const float8 one = {1.f, 1.f, 1.f, 1.f, 1.f, 1.f, 1.f, 1.f};
    const float8 c0 = {0.31938153f, 0.31938153f, 0.31938153f, 0.31938153f, 0.31938153f, 0.31938153f, 0.31938153f, 0.31938153f};
    const float8 c1 = {0.356563782f, 0.356563782f, 0.356563782f, 0.356563782f, 0.356563782f, 0.356563782f, 0.356563782f, 0.356563782f};
    const float8 c2 = {1.781477937f, 1.781477937f, 1.781477937f, 1.781477937f, 1.781477937f, 1.781477937f, 1.781477937f, 1.781477937f};
    const float8 c3 = {-1.821255978f, -1.821255978f, -1.821255978f, -1.821255978f, -1.821255978f, -1.821255978f, -1.821255978f, -1.821255978f};
    const float8 c4 = {1.330274429f, 1.330274429f, 1.330274429f, 1.330274429f, 1.330274429f, 1.330274429f, 1.330274429f, 1.330274429f};
    const float8 invSqrt2Pi = {0.39894228040f, 0.39894228040f, 0.39894228040f, 0.39894228040f, 0.39894228040f, 0.39894228040f, 0.39894228040f, 0.39894228040f};
    const float8 coefficient = {0.2316419f, 0.2316419f, 0.2316419f, 0.2316419f, 0.2316419f, 0.2316419f, 0.2316419f, 0.2316419f};
    const float8 half = {0.5f, 0.5f, 0.5f, 0.5f, 0.5f, 0.5f, 0.5f, 0.5f};

    const __m256 xVec = _mm256_loadu_ps(&x[0]);
    const __m256 absMask = _mm256_castsi256_ps(_mm256_set1_epi32(0x7fffffff));
    float8 L;
    _mm256_storeu_ps(&L[0], _mm256_and_ps(xVec, absMask));

    float8 k = one / (one + coefficient * L);
    float8 polynomial = ((((c4 * k + c3) * k + c2) * k - c1) * k + c0);
    float8 w = polynomial * k;

    float8 densityArg;
    for (int lane = 0; lane < 8; ++lane)
        densityArg[lane] = -L[lane] * L[lane] * half[lane];
    float8 density = exp8(densityArg);
    w *= invSqrt2Pi * density;

    const __m256 wVec = _mm256_loadu_ps(&w[0]);
    const __m256 positive = _mm256_cmp_ps(xVec, _mm256_setzero_ps(), _CMP_GT_OQ);
    const __m256 complement = _mm256_sub_ps(_mm256_set1_ps(1.f), wVec);
    _mm256_storeu_ps(&w[0], _mm256_blendv_ps(wVec, complement, positive));
    return w;
}

static inline void black_scholes_block8(const float Sa[], const float Xa[],
                                        const float Ta[], const float ra[],
                                        const float va[], float result[], int i) {
    float8 S, X, T, r, v;
    std::memcpy(&S, Sa + i, sizeof(S));
    std::memcpy(&X, Xa + i, sizeof(X));
    std::memcpy(&T, Ta + i, sizeof(T));
    std::memcpy(&r, ra + i, sizeof(r));
    std::memcpy(&v, va + i, sizeof(v));

    const float8 half = {0.5f, 0.5f, 0.5f, 0.5f, 0.5f, 0.5f, 0.5f, 0.5f};
    float8 ratio = S / X;
    float8 logRatio, sqrtT;
    for (int lane = 0; lane < 8; ++lane) {
        logRatio[lane] = logf(ratio[lane]);
    }
    _mm256_storeu_ps(&sqrtT[0], _mm256_sqrt_ps(_mm256_loadu_ps(&T[0])));

    float8 d1 = (logRatio + (r + v * v * half) * T) / (v * sqrtT);
    float8 d2 = d1 - v * sqrtT;
    float8 discountArg = (-r) * T;
    float8 discount = exp8(discountArg);

    float8 values = S * CND8(d1) - X * discount * CND8(d2);
    std::memcpy(result + i, &values, sizeof(values));
}
#endif
#endif

void black_scholes(float Sa[], float Xa[], float Ta[], float ra[], float va[],
                   float result[], int count, int threads) {
#if (defined(__GNUC__) || defined(__clang__)) && defined(__AVX__)
    const int blocks8 = count / 8;
    const int hasFourLaneBlock = (count - blocks8 * 8) >= 4;
    const int blocks = blocks8 + (hasFourLaneBlock ? 1 : 0);
    if (threads > 1 && blocks > 0) {
        // Each iteration writes a disjoint vector block.
        #pragma omp parallel for schedule(static) num_threads(threads)
        for (int block = 0; block < blocks; ++block) {
            if (block < blocks8)
                black_scholes_block8(Sa, Xa, Ta, ra, va, result, block * 8);
            else
                black_scholes_block4(Sa, Xa, Ta, ra, va, result, blocks8 * 8);
        }
    } else {
        for (int block = 0; block < blocks; ++block) {
            if (block < blocks8)
                black_scholes_block8(Sa, Xa, Ta, ra, va, result, block * 8);
            else
                black_scholes_block4(Sa, Xa, Ta, ra, va, result, blocks8 * 8);
        }
    }

    const int vectorCount = blocks8 * 8 + (hasFourLaneBlock ? 4 : 0);
    for (int i = vectorCount; i < count; ++i)
        black_scholes_element(Sa, Xa, Ta, ra, va, result, i);
#elif defined(__GNUC__) || defined(__clang__)
    const int blocks = count / 4;
    if (threads > 1 && blocks > 0) {
        // Each iteration writes four distinct output elements.
        #pragma omp parallel for schedule(static) num_threads(threads)
        for (int block = 0; block < blocks; ++block)
            black_scholes_block4(Sa, Xa, Ta, ra, va, result, block * 4);
    } else {
        for (int block = 0; block < blocks; ++block)
            black_scholes_block4(Sa, Xa, Ta, ra, va, result, block * 4);
    }

    for (int i = blocks * 4; i < count; ++i)
        black_scholes_element(Sa, Xa, Ta, ra, va, result, i);
#else
    if (threads <= 1) {
        for (int i = 0; i < count; ++i)
            black_scholes_element(Sa, Xa, Ta, ra, va, result, i);
        return;
    }

    #pragma omp parallel for schedule(static) num_threads(threads)
    for (int i = 0; i < count; ++i)
        black_scholes_element(Sa, Xa, Ta, ra, va, result, i);
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

extern "C" void run(const void* input1, const void* input2, void* output,
                    int n, int parameter, int threads) {
    float* a = (float*)input1;
    black_scholes(a, a + n, a + 2 * n, a + 3 * n, a + 4 * n,
                  (float*)output, n, threads);
}

// Candidate retains a44's bounded exp path and tests packed sqrt in SIMD blocks.
