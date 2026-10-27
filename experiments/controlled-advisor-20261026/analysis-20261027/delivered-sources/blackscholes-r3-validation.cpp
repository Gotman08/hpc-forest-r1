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
#include <cfloat>
#include <omp.h>

#if (defined(__GNUC__) || defined(__clang__)) && \
    (defined(__x86_64__) || defined(__i386__))
#include <immintrin.h>
#define BS_CAN_BUILD_AVX2 1
#define BS_AVX2_INLINE __attribute__((target("avx2"), always_inline)) inline
#define BS_AVX2_FUNCTION __attribute__((target("avx2")))
#else
#define BS_CAN_BUILD_AVX2 0
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

#if BS_CAN_BUILD_AVX2

static BS_AVX2_INLINE __m256 bs_abs_ps(__m256 x) {
    return _mm256_andnot_ps(_mm256_set1_ps(-0.0f), x);
}

static BS_AVX2_INLINE bool bs_all_lanes(__m256 mask) {
    return _mm256_movemask_ps(mask) == 0xff;
}

// Natural-log approximation for positive, normal inputs. Range reduction
// maps the mantissa to [sqrt(1/2), sqrt(2)], then uses the atanh series.
static BS_AVX2_INLINE __m256 bs_log_positive_ps(__m256 x) {
    const __m256 one = _mm256_set1_ps(1.0f);
    __m256i bits = _mm256_castps_si256(x);
    __m256i exponent = _mm256_sub_epi32(
        _mm256_and_si256(_mm256_srli_epi32(bits, 23), _mm256_set1_epi32(255)),
        _mm256_set1_epi32(127));
    __m256 mantissa = _mm256_castsi256_ps(_mm256_or_si256(
        _mm256_and_si256(bits, _mm256_set1_epi32(0x007fffff)),
        _mm256_set1_epi32(0x3f800000)));

    __m256 adjust = _mm256_cmp_ps(mantissa, _mm256_set1_ps(1.4142135623730951f), _CMP_GT_OQ);
    __m256i adjust_i = _mm256_and_si256(_mm256_castps_si256(adjust), _mm256_set1_epi32(1));
    exponent = _mm256_add_epi32(exponent, adjust_i);
    mantissa = _mm256_blendv_ps(mantissa, _mm256_mul_ps(mantissa, _mm256_set1_ps(0.5f)), adjust);

    __m256 y = _mm256_div_ps(_mm256_sub_ps(mantissa, one), _mm256_add_ps(mantissa, one));
    __m256 y2 = _mm256_mul_ps(y, y);
    __m256 p = _mm256_set1_ps(1.0f / 13.0f);
    p = _mm256_add_ps(_mm256_mul_ps(p, y2), _mm256_set1_ps(1.0f / 11.0f));
    p = _mm256_add_ps(_mm256_mul_ps(p, y2), _mm256_set1_ps(1.0f / 9.0f));
    p = _mm256_add_ps(_mm256_mul_ps(p, y2), _mm256_set1_ps(1.0f / 7.0f));
    p = _mm256_add_ps(_mm256_mul_ps(p, y2), _mm256_set1_ps(1.0f / 5.0f));
    p = _mm256_add_ps(_mm256_mul_ps(p, y2), _mm256_set1_ps(1.0f / 3.0f));
    p = _mm256_add_ps(_mm256_mul_ps(p, y2), one);
    __m256 log_mantissa = _mm256_mul_ps(_mm256_set1_ps(2.0f), _mm256_mul_ps(y, p));
    __m256 log_exponent = _mm256_mul_ps(_mm256_cvtepi32_ps(exponent), _mm256_set1_ps(0.6931471805599453f));
    return _mm256_add_ps(log_mantissa, log_exponent);
}

// Exponential approximation for arguments in [-70, 70]. Split ln(2) keeps
// range-reduction error small; the degree-eight Taylor polynomial is evaluated
// with packed arithmetic, without vector transcendental calls.
static BS_AVX2_INLINE __m256 bs_exp_bounded_ps(__m256 x) {
    __m256 scaled = _mm256_mul_ps(x, _mm256_set1_ps(1.4426950408889634f));
    __m256 rounded = _mm256_round_ps(scaled, _MM_FROUND_TO_NEAREST_INT | _MM_FROUND_NO_EXC);
    __m256i ki = _mm256_cvttps_epi32(rounded);
    __m256 k = _mm256_cvtepi32_ps(ki);
    __m256 r = _mm256_sub_ps(x, _mm256_mul_ps(k, _mm256_set1_ps(0.693145751953125f)));
    r = _mm256_sub_ps(r, _mm256_mul_ps(k, _mm256_set1_ps(1.428606765330187e-6f)));

    __m256 p = _mm256_set1_ps(1.0f / 40320.0f);
    p = _mm256_add_ps(_mm256_mul_ps(p, r), _mm256_set1_ps(1.0f / 5040.0f));
    p = _mm256_add_ps(_mm256_mul_ps(p, r), _mm256_set1_ps(1.0f / 720.0f));
    p = _mm256_add_ps(_mm256_mul_ps(p, r), _mm256_set1_ps(1.0f / 120.0f));
    p = _mm256_add_ps(_mm256_mul_ps(p, r), _mm256_set1_ps(1.0f / 24.0f));
    p = _mm256_add_ps(_mm256_mul_ps(p, r), _mm256_set1_ps(1.0f / 6.0f));
    p = _mm256_add_ps(_mm256_mul_ps(p, r), _mm256_set1_ps(0.5f));
    p = _mm256_add_ps(_mm256_mul_ps(p, r), _mm256_set1_ps(1.0f));
    p = _mm256_add_ps(_mm256_mul_ps(p, r), _mm256_set1_ps(1.0f));

    __m256i scale_bits = _mm256_slli_epi32(
        _mm256_add_epi32(ki, _mm256_set1_epi32(127)), 23);
    return _mm256_mul_ps(p, _mm256_castsi256_ps(scale_bits));
}

static BS_AVX2_INLINE __m256 bs_cnd_ps(__m256 x) {
    const __m256 one = _mm256_set1_ps(1.0f);
    __m256 L = bs_abs_ps(x);
    __m256 k = _mm256_div_ps(one, _mm256_add_ps(one, _mm256_mul_ps(_mm256_set1_ps(0.2316419f), L)));
    __m256 k2 = _mm256_mul_ps(k, k);
    __m256 k3 = _mm256_mul_ps(k2, k);
    __m256 k4 = _mm256_mul_ps(k2, k2);
    __m256 k5 = _mm256_mul_ps(k3, k2);

    __m256 w = _mm256_sub_ps(_mm256_mul_ps(_mm256_set1_ps(0.31938153f), k),
                              _mm256_mul_ps(_mm256_set1_ps(0.356563782f), k2));
    w = _mm256_add_ps(w, _mm256_mul_ps(_mm256_set1_ps(1.781477937f), k3));
    w = _mm256_sub_ps(w, _mm256_mul_ps(_mm256_set1_ps(1.821255978f), k4));
    w = _mm256_add_ps(w, _mm256_mul_ps(_mm256_set1_ps(1.330274429f), k5));

    __m256 exp_arg = _mm256_mul_ps(_mm256_mul_ps(L, L), _mm256_set1_ps(-0.5f));
    w = _mm256_mul_ps(w, _mm256_mul_ps(_mm256_set1_ps(0.39894228040f), bs_exp_bounded_ps(exp_arg)));
    __m256 positive = _mm256_cmp_ps(x, _mm256_setzero_ps(), _CMP_GT_OQ);
    return _mm256_blendv_ps(w, _mm256_sub_ps(one, w), positive);
}

static BS_AVX2_INLINE void bs_process_eight_avx2(
    const float* Sa, const float* Xa, const float* Ta, const float* ra,
    const float* va, float* result, int base) {
    __m256 S = _mm256_loadu_ps(Sa + base);
    __m256 X = _mm256_loadu_ps(Xa + base);
    __m256 T = _mm256_loadu_ps(Ta + base);
    __m256 r = _mm256_loadu_ps(ra + base);
    __m256 v = _mm256_loadu_ps(va + base);
    const __m256 zero = _mm256_setzero_ps();
    const __m256 max_float = _mm256_set1_ps(FLT_MAX);

    __m256 safe = _mm256_and_ps(
        _mm256_and_ps(_mm256_cmp_ps(bs_abs_ps(S), max_float, _CMP_LE_OQ),
                      _mm256_cmp_ps(bs_abs_ps(X), max_float, _CMP_LE_OQ)),
        _mm256_and_ps(_mm256_cmp_ps(bs_abs_ps(T), max_float, _CMP_LE_OQ),
                      _mm256_and_ps(_mm256_cmp_ps(bs_abs_ps(r), max_float, _CMP_LE_OQ),
                                    _mm256_cmp_ps(bs_abs_ps(v), max_float, _CMP_LE_OQ))));
    safe = _mm256_and_ps(safe, _mm256_cmp_ps(S, zero, _CMP_GT_OQ));
    safe = _mm256_and_ps(safe, _mm256_cmp_ps(X, zero, _CMP_GT_OQ));
    safe = _mm256_and_ps(safe, _mm256_cmp_ps(T, zero, _CMP_GT_OQ));
    safe = _mm256_and_ps(safe, _mm256_cmp_ps(v, zero, _CMP_GT_OQ));
    if (!bs_all_lanes(safe)) {
        black_scholes_serial(const_cast<float*>(Sa + base), const_cast<float*>(Xa + base),
                             const_cast<float*>(Ta + base), const_cast<float*>(ra + base),
                             const_cast<float*>(va + base), result + base, 8);
        return;
    }

    __m256 ratio = _mm256_div_ps(S, X);
    safe = _mm256_and_ps(_mm256_cmp_ps(ratio, _mm256_set1_ps(8.673617379884035e-19f), _CMP_GE_OQ),
                         _mm256_cmp_ps(ratio, _mm256_set1_ps(1.152921504606847e18f), _CMP_LE_OQ));
    if (!bs_all_lanes(safe)) {
        black_scholes_serial(const_cast<float*>(Sa + base), const_cast<float*>(Xa + base),
                             const_cast<float*>(Ta + base), const_cast<float*>(ra + base),
                             const_cast<float*>(va + base), result + base, 8);
        return;
    }

    __m256 log_ratio = bs_log_positive_ps(ratio);
    __m256 root_T = _mm256_sqrt_ps(T);
    __m256 denominator = _mm256_mul_ps(v, root_T);
    __m256 drift = _mm256_add_ps(r, _mm256_mul_ps(_mm256_mul_ps(v, v), _mm256_set1_ps(0.5f)));
    __m256 d1 = _mm256_div_ps(_mm256_add_ps(log_ratio, _mm256_mul_ps(drift, T)), denominator);
    __m256 d2 = _mm256_sub_ps(d1, denominator);
    __m256 discount_arg = _mm256_sub_ps(zero, _mm256_mul_ps(r, T));

    safe = _mm256_and_ps(_mm256_cmp_ps(denominator, _mm256_set1_ps(1.0e-30f), _CMP_GE_OQ),
                         _mm256_cmp_ps(denominator, max_float, _CMP_LE_OQ));
    safe = _mm256_and_ps(safe, _mm256_cmp_ps(bs_abs_ps(d1), _mm256_set1_ps(8.0f), _CMP_LE_OQ));
    safe = _mm256_and_ps(safe, _mm256_cmp_ps(bs_abs_ps(d2), _mm256_set1_ps(8.0f), _CMP_LE_OQ));
    safe = _mm256_and_ps(safe, _mm256_cmp_ps(discount_arg, _mm256_set1_ps(-70.0f), _CMP_GE_OQ));
    safe = _mm256_and_ps(safe, _mm256_cmp_ps(discount_arg, _mm256_set1_ps(70.0f), _CMP_LE_OQ));
    if (!bs_all_lanes(safe)) {
        black_scholes_serial(const_cast<float*>(Sa + base), const_cast<float*>(Xa + base),
                             const_cast<float*>(Ta + base), const_cast<float*>(ra + base),
                             const_cast<float*>(va + base), result + base, 8);
        return;
    }

    __m256 discount = bs_exp_bounded_ps(discount_arg);
    __m256 price = _mm256_sub_ps(
        _mm256_mul_ps(S, bs_cnd_ps(d1)),
        _mm256_mul_ps(_mm256_mul_ps(X, discount), bs_cnd_ps(d2)));
    if (!bs_all_lanes(_mm256_cmp_ps(bs_abs_ps(price), max_float, _CMP_LE_OQ))) {
        black_scholes_serial(const_cast<float*>(Sa + base), const_cast<float*>(Xa + base),
                             const_cast<float*>(Ta + base), const_cast<float*>(ra + base),
                             const_cast<float*>(va + base), result + base, 8);
        return;
    }
    _mm256_storeu_ps(result + base, price);
}

static BS_AVX2_FUNCTION void black_scholes_avx2(float Sa[], float Xa[], float Ta[],
                                                 float ra[], float va[], float result[],
                                                 int count) {
    int i = 0;
    // Two independent eight-lane blocks expose more independent work while
    // keeping the kernel stateless and usable inside a caller's threaded loop.
    for (; i <= count - 16; i += 16) {
        bs_process_eight_avx2(Sa, Xa, Ta, ra, va, result, i);
        bs_process_eight_avx2(Sa, Xa, Ta, ra, va, result, i + 8);
    }
    for (; i <= count - 8; i += 8)
        bs_process_eight_avx2(Sa, Xa, Ta, ra, va, result, i);
    for (; i < count; ++i)
        black_scholes_serial(Sa + i, Xa + i, Ta + i, ra + i, va + i, result + i, 1);
}

static bool bs_avx2_supported() {
    __builtin_cpu_init();
    return __builtin_cpu_supports("avx2");
}

#endif

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
    (void)input2;
    (void)parameter;
    if (n <= 0)
        return;

    float* a = (float*)input1;
    float* Sa = a;
    float* Xa = a + n;
    float* Ta = a + 2 * n;
    float* ra = a + 3 * n;
    float* va = a + 4 * n;
    float* result = (float*)output;

#if BS_CAN_BUILD_AVX2
    const bool use_avx2 = bs_avx2_supported();
#endif

    if (threads <= 1) {
#if BS_CAN_BUILD_AVX2
        if (use_avx2) {
            black_scholes_avx2(Sa, Xa, Ta, ra, va, result, n);
            return;
        }
#endif
        black_scholes_serial(Sa, Xa, Ta, ra, va, result, n);
        return;
    }

    const int team_size = std::min(n, threads);
    // Avoid team setup when each requested worker would receive little work.
    if (n / team_size < 1024) {
#if BS_CAN_BUILD_AVX2
        if (use_avx2) {
            black_scholes_avx2(Sa, Xa, Ta, ra, va, result, n);
            return;
        }
#endif
        black_scholes_serial(Sa, Xa, Ta, ra, va, result, n);
        return;
    }

#if BS_CAN_BUILD_AVX2
    if (use_avx2) {
        // Partition complete 16-element SIMD chunks among the actual team.
        // This keeps each worker's AVX2 range tail-free; process the global
        // remainder after the parallel region.
        const int block_count = n / 16;
        #pragma omp parallel num_threads(team_size)
        {
            const int worker = omp_get_thread_num();
            const int actual_team_size = omp_get_num_threads();
            const int blocks_per_worker = block_count / actual_team_size;
            const int extra_blocks = block_count % actual_team_size;
            const int first_block = worker * blocks_per_worker + std::min(worker, extra_blocks);
            const int worker_blocks = blocks_per_worker + (worker < extra_blocks ? 1 : 0);
            const int begin = first_block * 16;
            const int count = worker_blocks * 16;

            black_scholes_avx2(Sa + begin, Xa + begin, Ta + begin, ra + begin,
                               va + begin, result + begin, count);
        }

        const int tail = block_count * 16;
        if (tail < n)
            black_scholes_serial(Sa + tail, Xa + tail, Ta + tail, ra + tail,
                                 va + tail, result + tail, n - tail);
        return;
    }
#endif

    // Scalar fallback also honors the caller's budget and partitions using the
    // actual team size in case the runtime creates fewer workers than requested.
    #pragma omp parallel num_threads(team_size)
    {
        const int worker = omp_get_thread_num();
        const int actual_team_size = omp_get_num_threads();
        const int block_size = n / actual_team_size;
        const int remainder = n % actual_team_size;
        const int begin = worker * block_size + std::min(worker, remainder);
        const int count = block_size + (worker < remainder ? 1 : 0);

        black_scholes_serial(Sa + begin, Xa + begin, Ta + begin, ra + begin,
                             va + begin, result + begin, count);
    }
}
