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
#include <omp.h>

#if defined(__AVX2__)
#include <immintrin.h>
#endif

#if defined(_OPENMP) && _OPENMP >= 201307
#pragma omp declare simd notinbranch
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

static inline float black_scholes_one(float S, float X, float T, float r, float v) {
    float d1 = (logf(S / X) + (r + v * v * .5f) * T) / (v * sqrtf(T));
    float d2 = d1 - v * sqrtf(T);
    return S * CND(d1) - X * expf(-r * T) * CND(d2);
}

#if defined(__AVX2__)
// One Newton refinement makes the reciprocal estimate accurate to roughly
// single-precision rounding for the finite, nonzero denominators in the fast path.
static inline __m256 divide_refined_avx2(__m256 numerator, __m256 denominator) {
    const __m256 two = _mm256_set1_ps(2.f);
    __m256 reciprocal = _mm256_rcp_ps(denominator);
    reciprocal = _mm256_mul_ps(reciprocal,
                               _mm256_sub_ps(two, _mm256_mul_ps(denominator, reciprocal)));
    return _mm256_mul_ps(numerator, reciprocal);
}

// exp(x) for the bounded interval used by the fast path. Range reduction
// leaves a small remainder for the Taylor polynomial; callers use scalar
// evaluation for lanes outside the bounds established in the kernel.
static inline __m256 exp_approx_avx2(__m256 x) {
    const __m256 log2e = _mm256_set1_ps(1.4426950408889634f);
    const __m256 ln2_hi = _mm256_set1_ps(0.693145751953125f);
    const __m256 ln2_lo = _mm256_set1_ps(1.428606765330187e-6f);
    __m256 scaled = _mm256_mul_ps(x, log2e);
    __m256 rounded = _mm256_round_ps(scaled, _MM_FROUND_TO_NEAREST_INT | _MM_FROUND_NO_EXC);
    __m256i exponent = _mm256_cvttps_epi32(rounded);
    __m256 ef = _mm256_cvtepi32_ps(exponent);

    __m256 remainder = _mm256_sub_ps(x, _mm256_mul_ps(ef, ln2_hi));
    remainder = _mm256_sub_ps(remainder, _mm256_mul_ps(ef, ln2_lo));

    __m256 p = _mm256_set1_ps(1.f / 5040.f);
    p = _mm256_add_ps(_mm256_set1_ps(1.f / 720.f), _mm256_mul_ps(remainder, p));
    p = _mm256_add_ps(_mm256_set1_ps(1.f / 120.f), _mm256_mul_ps(remainder, p));
    p = _mm256_add_ps(_mm256_set1_ps(1.f / 24.f), _mm256_mul_ps(remainder, p));
    p = _mm256_add_ps(_mm256_set1_ps(1.f / 6.f), _mm256_mul_ps(remainder, p));
    p = _mm256_add_ps(_mm256_set1_ps(.5f), _mm256_mul_ps(remainder, p));
    p = _mm256_add_ps(_mm256_set1_ps(1.f), _mm256_mul_ps(remainder, p));
    p = _mm256_add_ps(_mm256_set1_ps(1.f), _mm256_mul_ps(remainder, p));

    __m256i biased = _mm256_add_epi32(exponent, _mm256_set1_epi32(127));
    __m256 scale = _mm256_castsi256_ps(_mm256_slli_epi32(biased, 23));
    return _mm256_mul_ps(p, scale);
}

static inline __m256 cnd_avx2(__m256 x) {
    const __m256 sign_bit = _mm256_set1_ps(-0.0f);
    const __m256 zero = _mm256_setzero_ps();
    const __m256 one = _mm256_set1_ps(1.f);
    __m256 L = _mm256_andnot_ps(sign_bit, x);
    __m256 k = divide_refined_avx2(one, _mm256_add_ps(one, _mm256_mul_ps(_mm256_set1_ps(.2316419f), L)));
    __m256 k2 = _mm256_mul_ps(k, k);

    // Evaluate the CND polynomial in paired factors using k^2.
    __m256 p0 = _mm256_sub_ps(_mm256_set1_ps(.31938153f),
                              _mm256_mul_ps(_mm256_set1_ps(.356563782f), k));
    __m256 p1 = _mm256_sub_ps(_mm256_set1_ps(1.781477937f),
                              _mm256_mul_ps(_mm256_set1_ps(1.821255978f), k));
    __m256 inner = _mm256_add_ps(p1,
                                 _mm256_mul_ps(k2, _mm256_set1_ps(1.330274429f)));
    __m256 w = _mm256_mul_ps(k,
                             _mm256_add_ps(p0, _mm256_mul_ps(k2, inner)));

    __m256 exponent = _mm256_mul_ps(_mm256_set1_ps(-.5f), _mm256_mul_ps(L, L));
    w = _mm256_mul_ps(w, _mm256_set1_ps(.39894228040f));
    w = _mm256_mul_ps(w, exp_approx_avx2(exponent));

    __m256 positive = _mm256_cmp_ps(x, zero, _CMP_GT_OQ);
    return _mm256_blendv_ps(w, _mm256_sub_ps(one, w), positive);
}
#endif

void black_scholes_serial(float Sa[], float Xa[], float Ta[], float ra[], float va[], float result[], int count) {
    int i = 0;
#if defined(__AVX2__)
    const __m256 zero = _mm256_setzero_ps();
    const __m256 one = _mm256_set1_ps(1.f);
    const __m256 min_input = _mm256_set1_ps(1.e-6f);
    const __m256 max_input = _mm256_set1_ps(1.e6f);
    const __m256 min_t = _mm256_set1_ps(.01f);
    const __m256 max_t = _mm256_set1_ps(100.f);
    const __m256 min_v = _mm256_set1_ps(.05f);
    const __m256 max_v = _mm256_set1_ps(3.f);
    const __m256 min_r = _mm256_set1_ps(-1.f);
    const __m256 max_r = _mm256_set1_ps(1.f);
    const __m256 min_ratio = _mm256_set1_ps(.5f);
    const __m256 max_ratio = _mm256_set1_ps(2.f);
    const __m256 min_rt = _mm256_set1_ps(-10.f);
    const __m256 max_rt = _mm256_set1_ps(10.f);
    const __m256 max_d = _mm256_set1_ps(5.5f);
    const __m256 sign_bit = _mm256_set1_ps(-0.0f);

    for (; i < count && count - i >= 8; i += 8) {
        // Every array may have a different alignment because its offset is n
        // floats from the 64-byte-aligned input1 base.
        __m256 s = _mm256_loadu_ps(Sa + i);
        __m256 x = _mm256_loadu_ps(Xa + i);
        __m256 t = _mm256_loadu_ps(Ta + i);
        __m256 r = _mm256_loadu_ps(ra + i);
        __m256 v = _mm256_loadu_ps(va + i);

        __m256 preliminary = _mm256_and_ps(
            _mm256_and_ps(
                _mm256_and_ps(
                    _mm256_and_ps(
                        _mm256_and_ps(_mm256_cmp_ps(s, min_input, _CMP_GE_OQ), _mm256_cmp_ps(s, max_input, _CMP_LE_OQ)),
                        _mm256_and_ps(_mm256_cmp_ps(x, min_input, _CMP_GE_OQ), _mm256_cmp_ps(x, max_input, _CMP_LE_OQ))),
                    _mm256_and_ps(_mm256_cmp_ps(t, min_t, _CMP_GE_OQ), _mm256_cmp_ps(t, max_t, _CMP_LE_OQ))),
                _mm256_and_ps(_mm256_cmp_ps(v, min_v, _CMP_GE_OQ), _mm256_cmp_ps(v, max_v, _CMP_LE_OQ))),
            _mm256_and_ps(_mm256_cmp_ps(r, min_r, _CMP_GE_OQ), _mm256_cmp_ps(r, max_r, _CMP_LE_OQ)));

        // Sanitize rejected lanes before divisions and approximations. Only
        // lanes meeting all range checks can be accepted by the vector path.
        __m256 s0 = _mm256_blendv_ps(one, s, preliminary);
        __m256 x0 = _mm256_blendv_ps(one, x, preliminary);
        __m256 ratio0 = divide_refined_avx2(s0, x0);
        __m256 ratio_ok = _mm256_and_ps(_mm256_cmp_ps(ratio0, min_ratio, _CMP_GE_OQ),
                                        _mm256_cmp_ps(ratio0, max_ratio, _CMP_LE_OQ));
        __m256 base_safe = _mm256_and_ps(preliminary, ratio_ok);
        __m256 t0 = _mm256_blendv_ps(one, t, base_safe);
        __m256 r0 = _mm256_blendv_ps(zero, r, base_safe);
        __m256 rt0 = _mm256_mul_ps(r0, t0);
        __m256 rt_ok = _mm256_and_ps(_mm256_cmp_ps(rt0, min_rt, _CMP_GE_OQ),
                                     _mm256_cmp_ps(rt0, max_rt, _CMP_LE_OQ));
        __m256 fast_safe = _mm256_and_ps(base_safe, rt_ok);

        __m256 sf = _mm256_blendv_ps(one, s, fast_safe);
        __m256 xf = _mm256_blendv_ps(one, x, fast_safe);
        __m256 tf = _mm256_blendv_ps(one, t, fast_safe);
        __m256 rf = _mm256_blendv_ps(zero, r, fast_safe);
        __m256 vf = _mm256_blendv_ps(one, v, fast_safe);
        __m256 ratio = divide_refined_avx2(sf, xf);

        // log(ratio) = 2 * (z + z^3/3 + ...), z=(ratio-1)/(ratio+1).
        // The selected ratio interval bounds |z| by 1/3.
        __m256 z = divide_refined_avx2(_mm256_sub_ps(ratio, one), _mm256_add_ps(ratio, one));
        __m256 z2 = _mm256_mul_ps(z, z);
        __m256 log_poly = _mm256_set1_ps(1.f / 11.f);
        log_poly = _mm256_add_ps(_mm256_set1_ps(1.f / 9.f), _mm256_mul_ps(z2, log_poly));
        log_poly = _mm256_add_ps(_mm256_set1_ps(1.f / 7.f), _mm256_mul_ps(z2, log_poly));
        log_poly = _mm256_add_ps(_mm256_set1_ps(1.f / 5.f), _mm256_mul_ps(z2, log_poly));
        log_poly = _mm256_add_ps(_mm256_set1_ps(1.f / 3.f), _mm256_mul_ps(z2, log_poly));
        __m256 log_ratio = _mm256_mul_ps(_mm256_set1_ps(2.f), _mm256_mul_ps(z, _mm256_add_ps(one, _mm256_mul_ps(z2, log_poly))));

        __m256 sqrt_t = _mm256_sqrt_ps(tf);
        __m256 v2 = _mm256_mul_ps(vf, vf);
        __m256 drift = _mm256_mul_ps(_mm256_add_ps(rf, _mm256_mul_ps(v2, _mm256_set1_ps(.5f))), tf);
        __m256 d1 = divide_refined_avx2(_mm256_add_ps(log_ratio, drift), _mm256_mul_ps(vf, sqrt_t));
        __m256 d2 = _mm256_sub_ps(d1, _mm256_mul_ps(vf, sqrt_t));
        __m256 d1_ok = _mm256_cmp_ps(_mm256_andnot_ps(sign_bit, d1), max_d, _CMP_LE_OQ);
        __m256 d2_ok = _mm256_cmp_ps(_mm256_andnot_ps(sign_bit, d2), max_d, _CMP_LE_OQ);
        __m256 fast_lanes = _mm256_and_ps(fast_safe, _mm256_and_ps(d1_ok, d2_ok));
        __m256 d1_safe = _mm256_blendv_ps(zero, d1, fast_lanes);
        __m256 d2_safe = _mm256_blendv_ps(zero, d2, fast_lanes);

        __m256 c1 = cnd_avx2(d1_safe);
        __m256 c2 = cnd_avx2(d2_safe);
        __m256 discount = exp_approx_avx2(_mm256_sub_ps(zero, _mm256_mul_ps(rf, tf)));
        __m256 value = _mm256_sub_ps(_mm256_mul_ps(sf, c1),
                                     _mm256_mul_ps(_mm256_mul_ps(xf, discount), c2));
        _mm256_storeu_ps(result + i, value);

        unsigned int safe_bits = (unsigned int)_mm256_movemask_ps(fast_lanes);
        if (safe_bits != 0xffu) {
            // Transfer only rejected lanes to the exact scalar implementation.
            for (int lane = 0; lane < 8; ++lane) {
                if ((safe_bits & (1u << lane)) == 0) {
                    int j = i + lane;
                    result[j] = black_scholes_one(Sa[j], Xa[j], Ta[j], ra[j], va[j]);
                }
            }
        }
    }
#endif

    // Scalar fallback handles arbitrary tails and is also the entire path when
    // this translation unit is built without AVX2.
    for (; i < count; ++i)
        result[i] = black_scholes_one(Sa[i], Xa[i], Ta[i], ra[i], va[i]);
}

void black_scholes_parallel(float Sa[], float Xa[], float Ta[], float ra[], float va[], float result[], int count, int threads) {
    if (count <= 0)
        return;
    if (threads <= 1 || count <= 1) {
        black_scholes_serial(Sa, Xa, Ta, ra, va, result, count);
        return;
    }

    const int requested_threads = std::min(threads, count);
    #pragma omp parallel num_threads(requested_threads)
    {
        const int worker = omp_get_thread_num();
        const int team_size = omp_get_num_threads();
        const int quotient = count / team_size;
        const int remainder = count % team_size;
        const int begin = worker * quotient + std::min(worker, remainder);
        const int end = begin + quotient + (worker < remainder ? 1 : 0);

        black_scholes_serial(Sa + begin, Xa + begin, Ta + begin, ra + begin, va + begin, result + begin, end - begin);
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
    if (n <= 0)
        return;
    float* a = (float*)input1;
    black_scholes_parallel(a, a + n, a + 2 * n, a + 3 * n, a + 4 * n, (float*)output, n, threads);
}
