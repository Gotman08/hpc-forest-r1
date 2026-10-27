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
#include <cstdint>
#include <cstring>
#include <cmath>
#include <algorithm>
#include <omp.h>

#if defined(__GNUC__) || defined(__clang__)
typedef float v4sf __attribute__((vector_size(16)));

#if defined(__linux__) && defined(__x86_64__) && defined(__GLIBC__) && ((__GLIBC__ > 2) || (__GLIBC__ == 2 && __GLIBC_MINOR__ >= 22))
extern "C" v4sf _ZGVbN4v_expf(v4sf);
#define HAVE_LIBMVEC_EXP4 1
#if defined(__AVX2__)
typedef float v8sf __attribute__((vector_size(32)));
extern "C" v8sf _ZGVdN8v_expf(v8sf);
#define HAVE_LIBMVEC_EXP8 1
#endif
#endif

// Prepare two independent CND inputs before issuing their vector exponentials.
static inline void CND4_prepare(v4sf X, v4sf& L, v4sf& exp_arg) {
    for (int lane = 0; lane < 4; ++lane) {
        L[lane] = fabsf(X[lane]);
        exp_arg[lane] = -L[lane] * L[lane] * .5f;
    }
}

// Keep the CND polynomial in the same Horner form.
static inline v4sf CND4_finish(v4sf X, v4sf L, v4sf E) {
    const v4sf k = 1.f / (1.f + 0.2316419f * L);
    const float invSqrt2Pi = 0.39894228040f;
    v4sf w = k * (0.31938153f + k * (-0.356563782f + k * (1.781477937f + k * (-1.821255978f + k * 1.330274429f))));
    w *= invSqrt2Pi * E;

    v4sf answer;
    for (int lane = 0; lane < 4; ++lane)
        answer[lane] = X[lane] > 0.f ? 1.f - w[lane] : w[lane];
    return answer;
}

// Group the two independent CND exponentials for a Black-Scholes block.
static inline void CND4_pair(v4sf X1, v4sf X2, v4sf& answer1, v4sf& answer2) {
    v4sf L1, L2, exp_arg1, exp_arg2;
    CND4_prepare(X1, L1, exp_arg1);
    CND4_prepare(X2, L2, exp_arg2);

    v4sf E1, E2;
#if defined(HAVE_LIBMVEC_EXP4)
    E1 = _ZGVbN4v_expf(exp_arg1);
    E2 = _ZGVbN4v_expf(exp_arg2);
#else
    for (int lane = 0; lane < 4; ++lane) {
        E1[lane] = expf(exp_arg1[lane]);
        E2[lane] = expf(exp_arg2[lane]);
    }
#endif

    answer1 = CND4_finish(X1, L1, E1);
    answer2 = CND4_finish(X2, L2, E2);
}

#if defined(HAVE_LIBMVEC_EXP8)
// Pack the d1 and d2 CND exponent arguments into one AVX2 libmvec call.
static inline void CND4_pair_avx2(v4sf X1, v4sf X2, v4sf& answer1, v4sf& answer2) {
    v4sf L1, L2, exp_arg1, exp_arg2;
    CND4_prepare(X1, L1, exp_arg1);
    CND4_prepare(X2, L2, exp_arg2);

    v8sf packed_args;
    for (int lane = 0; lane < 4; ++lane) {
        packed_args[lane] = exp_arg1[lane];
        packed_args[lane + 4] = exp_arg2[lane];
    }
    const v8sf packed_exp = _ZGVdN8v_expf(packed_args);

    v4sf E1, E2;
    for (int lane = 0; lane < 4; ++lane) {
        E1[lane] = packed_exp[lane];
        E2[lane] = packed_exp[lane + 4];
    }
    answer1 = CND4_finish(X1, L1, E1);
    answer2 = CND4_finish(X2, L2, E2);
}
#endif
#endif

#if defined(__GNUC__) && (defined(__x86_64__) || defined(__i386__))
typedef float float8 __attribute__((vector_size(32)));

// Evaluate eight independent CND vectors, using libmvec for exponentials
// where available and retaining scalar expf as the portable fallback.
static inline void cnd_eight_vectors(const float8 x[8], float8 result[8]) {
    float abs_lanes[8][8];
    float exp_lanes[8][8];

    for (int lane = 0; lane < 8; ++lane) {
        for (int block = 0; block < 8; ++block) {
            float L = fabsf(x[block][lane]);
            abs_lanes[block][lane] = L;
#if !defined(HAVE_LIBMVEC_EXP4)
            exp_lanes[block][lane] = expf(-L * L * .5f);
#endif
        }
    }

#if defined(HAVE_LIBMVEC_EXP4)
    // Use the measured four-lane exp path for both halves of each 8-lane CND.
    for (int block = 0; block < 8; ++block) {
        v4sf low_arg, high_arg;
        for (int lane = 0; lane < 4; ++lane) {
            const float low_L = abs_lanes[block][lane];
            const float high_L = abs_lanes[block][lane + 4];
            low_arg[lane] = -low_L * low_L * .5f;
            high_arg[lane] = -high_L * high_L * .5f;
        }
        const v4sf low_exp = _ZGVbN4v_expf(low_arg);
        const v4sf high_exp = _ZGVbN4v_expf(high_arg);
        for (int lane = 0; lane < 4; ++lane) {
            exp_lanes[block][lane] = low_exp[lane];
            exp_lanes[block][lane + 4] = high_exp[lane];
        }
    }
#endif

    for (int block = 0; block < 8; ++block) {
        float8 L, exponential;
        std::memcpy(&L, abs_lanes[block], sizeof(L));
        std::memcpy(&exponential, exp_lanes[block], sizeof(exponential));

        float8 k = 1.f / (1.f + 0.2316419f * L);
        float8 k2 = k * k;
        float8 k3 = k2 * k;
        float8 k4 = k2 * k2;
        float8 k5 = k3 * k2;
        float8 w = (0.31938153f * k - 0.356563782f * k2 + 1.781477937f * k3 + -1.821255978f * k4 + 1.330274429f * k5);
        w *= 0.39894228040f * exponential;

        for (int lane = 0; lane < 8; ++lane) {
            if (x[block][lane] > 0.f)
                w[lane] = 1.f - w[lane];
        }
        result[block] = w;
    }
}

// Process four independent eight-lane blocks. Loads and stores intentionally
// use memcpy because each array's offset and the output need not be aligned.
static inline void black_scholes_32(float *Sa, float *Xa, float *Ta,
                                    float *ra, float *va, float *result,
                                    int base) {
    float8 S[4], X[4], T[4], r[4], v[4];
    float8 ratio[4], exponent[4], log_ratio[4], sqrt_T[4], discount[4];
    float log_lanes[4][8];
    float root_lanes[4][8];
    float discount_lanes[4][8];

    for (int block = 0; block < 4; ++block) {
        int offset = base + 8 * block;
        std::memcpy(&S[block], Sa + offset, sizeof(float8));
        std::memcpy(&X[block], Xa + offset, sizeof(float8));
        std::memcpy(&T[block], Ta + offset, sizeof(float8));
        std::memcpy(&r[block], ra + offset, sizeof(float8));
        std::memcpy(&v[block], va + offset, sizeof(float8));
        ratio[block] = S[block] / X[block];
        exponent[block] = (-r[block]) * T[block];
    }

    // Interleave scalar libm calls across the independent vector blocks.
    for (int lane = 0; lane < 8; ++lane) {
        for (int block = 0; block < 4; ++block) {
            log_lanes[block][lane] = logf(ratio[block][lane]);
            root_lanes[block][lane] = sqrtf(T[block][lane]);
            discount_lanes[block][lane] = expf(exponent[block][lane]);
        }
    }

    float8 cnd_input[8], cnd_result[8];
    for (int block = 0; block < 4; ++block) {
        std::memcpy(&log_ratio[block], log_lanes[block], sizeof(float8));
        std::memcpy(&sqrt_T[block], root_lanes[block], sizeof(float8));
        std::memcpy(&discount[block], discount_lanes[block], sizeof(float8));

        float8 v_sqrt_T = v[block] * sqrt_T[block];
        float8 drift = (r[block] + v[block] * v[block] * .5f) * T[block];
        cnd_input[block] = (log_ratio[block] + drift) / v_sqrt_T;
        cnd_input[block + 4] = cnd_input[block] - v_sqrt_T;
    }

    cnd_eight_vectors(cnd_input, cnd_result);

    for (int block = 0; block < 4; ++block) {
        float8 value = S[block] * cnd_result[block] -
                       (X[block] * discount[block]) * cnd_result[block + 4];
        std::memcpy(result + base + 8 * block, &value, sizeof(float8));
    }
}

// The eight-lane CND polynomial used by the bc307 kernel.
static inline float8 cnd_polynomial8_bc307(float8 x, float8 *exp_arg) {
    const float8 one = {1.f, 1.f, 1.f, 1.f, 1.f, 1.f, 1.f, 1.f};
    const float8 half = {.5f, .5f, .5f, .5f, .5f, .5f, .5f, .5f};
    const float8 c = {.2316419f, .2316419f, .2316419f, .2316419f,
                      .2316419f, .2316419f, .2316419f, .2316419f};
    const float8 a = {.31938153f, .31938153f, .31938153f, .31938153f,
                      .31938153f, .31938153f, .31938153f, .31938153f};
    const float8 b = {.356563782f, .356563782f, .356563782f, .356563782f,
                      .356563782f, .356563782f, .356563782f, .356563782f};
    const float8 d = {1.821255978f, 1.821255978f, 1.821255978f, 1.821255978f,
                      1.821255978f, 1.821255978f, 1.821255978f, 1.821255978f};
    const float8 e = {1.330274429f, 1.330274429f, 1.330274429f, 1.330274429f,
                      1.330274429f, 1.330274429f, 1.330274429f, 1.330274429f};
    const float8 c3 = {1.781477937f, 1.781477937f, 1.781477937f, 1.781477937f,
                       1.781477937f, 1.781477937f, 1.781477937f, 1.781477937f};

    float8 L;
    const int mask = 0x7fffffff;
    int lanes[8];
    std::memcpy(lanes, &x, sizeof(x));
    for (int lane = 0; lane < 8; ++lane)
        lanes[lane] &= mask;
    std::memcpy(&L, lanes, sizeof(L));

    float8 k = one / (one + c * L);
    float8 k2 = k * k;
    float8 k3 = k2 * k;
    float8 k4 = k2 * k2;
    float8 k5 = k3 * k2;
    *exp_arg = (-L * L) * half;
    return a * k - b * k2 + c3 * k3 - d * k4 + e * k5;
}

// bc307's four-by-eight SIMD kernel, with a scalar cleanup for every tail.
static inline void black_scholes_simd_bc307(float Sa[], float Xa[], float Ta[],
                                            float ra[], float va[], float result[],
                                            int count) {
    int i = 0;
    while (count - i >= 32) {
        float8 S[4], X[4], T[4], r[4], v[4], d1[4], d2[4];
        float ratios[32], log_ratios[32];
        float times[32], sqrt_times[32];
        float discount_args[32], discounts[32];
        float cnd_poly[64], cnd_exp_args[64], cnd_inputs[64];
        float cnd_exps[64], cnd_values[64];

        for (int block = 0; block < 4; ++block) {
            const int base = i + block * 8;
            std::memcpy(&S[block], Sa + base, sizeof(float8));
            std::memcpy(&X[block], Xa + base, sizeof(float8));
            std::memcpy(&T[block], Ta + base, sizeof(float8));
            std::memcpy(&r[block], ra + base, sizeof(float8));
            std::memcpy(&v[block], va + base, sizeof(float8));

            float8 ratio = S[block] / X[block];
            float8 discount_arg = (-r[block]) * T[block];
            std::memcpy(ratios + block * 8, &ratio, sizeof(float8));
            std::memcpy(times + block * 8, &T[block], sizeof(float8));
            std::memcpy(discount_args + block * 8, &discount_arg, sizeof(float8));
        }

#ifdef _OPENMP
#pragma omp simd
#endif
        for (int q = 0; q < 32; ++q) {
            log_ratios[q] = logf(ratios[q]);
            sqrt_times[q] = sqrtf(times[q]);
            discounts[q] = expf(discount_args[q]);
        }

        const float8 half = {.5f, .5f, .5f, .5f, .5f, .5f, .5f, .5f};
        for (int block = 0; block < 4; ++block) {
            float8 logv, sqrtv;
            std::memcpy(&logv, log_ratios + block * 8, sizeof(float8));
            std::memcpy(&sqrtv, sqrt_times + block * 8, sizeof(float8));
            float8 denom = v[block] * sqrtv;
            float8 drift = (r[block] + (v[block] * v[block]) * half) * T[block];
            d1[block] = (logv + drift) / denom;
            d2[block] = d1[block] - denom;

            float8 exp_arg1, exp_arg2;
            float8 poly1 = cnd_polynomial8_bc307(d1[block], &exp_arg1);
            float8 poly2 = cnd_polynomial8_bc307(d2[block], &exp_arg2);
            const int cnd_base = block * 16;
            std::memcpy(cnd_poly + cnd_base, &poly1, sizeof(float8));
            std::memcpy(cnd_poly + cnd_base + 8, &poly2, sizeof(float8));
            std::memcpy(cnd_exp_args + cnd_base, &exp_arg1, sizeof(float8));
            std::memcpy(cnd_exp_args + cnd_base + 8, &exp_arg2, sizeof(float8));
            std::memcpy(cnd_inputs + cnd_base, &d1[block], sizeof(float8));
            std::memcpy(cnd_inputs + cnd_base + 8, &d2[block], sizeof(float8));
        }

#ifdef _OPENMP
#pragma omp simd
#endif
        for (int q = 0; q < 64; ++q)
            cnd_exps[q] = expf(cnd_exp_args[q]);

        const float invSqrt2Pi = 0.39894228040f;
        for (int q = 0; q < 64; ++q) {
            float w = cnd_poly[q] * (invSqrt2Pi * cnd_exps[q]);
            if (cnd_inputs[q] > 0.f)
                w = 1.f - w;
            cnd_values[q] = w;
        }

        for (int block = 0; block < 4; ++block) {
            const int base = i + block * 8;
            const int cnd_base = block * 16;
            float8 nd1, nd2, discount;
            std::memcpy(&nd1, cnd_values + cnd_base, sizeof(float8));
            std::memcpy(&nd2, cnd_values + cnd_base + 8, sizeof(float8));
            std::memcpy(&discount, discounts + block * 8, sizeof(float8));
            float8 value = S[block] * nd1 - (X[block] * discount) * nd2;
            std::memcpy(result + base, &value, sizeof(float8));
        }
        i += 32;
    }

    black_scholes_serial(Sa + i, Xa + i, Ta + i, ra + i, va + i, result + i, count - i);
}
#endif

template <bool UseAvx2Exp>
static inline void black_scholes_range_impl(float* a, float* result, int n, int first, int last) {
#if defined(__GNUC__) || defined(__clang__)
    int i = first;
    for (; i <= last - 4; i += 4) {
        v4sf S, X, T, r, v;
        std::memcpy(&S, a + i, sizeof(S));
        std::memcpy(&X, a + n + i, sizeof(X));
        std::memcpy(&T, a + 2 * n + i, sizeof(T));
        std::memcpy(&r, a + 3 * n + i, sizeof(r));
        std::memcpy(&v, a + 4 * n + i, sizeof(v));

        v4sf log_ratio, sqrt_t, discount;
        for (int lane = 0; lane < 4; ++lane) {
            log_ratio[lane] = logf(S[lane] / X[lane]);
            sqrt_t[lane] = sqrtf(T[lane]);
            discount[lane] = expf(-r[lane] * T[lane]);
        }

        const v4sf v_sqrt_t = v * sqrt_t;
        const v4sf d1 = (log_ratio + (r + v * v * .5f) * T) / v_sqrt_t;
        const v4sf d2 = d1 - v_sqrt_t;
        v4sf cnd1, cnd2;
#if defined(HAVE_LIBMVEC_EXP8)
        if (UseAvx2Exp)
            CND4_pair_avx2(d1, d2, cnd1, cnd2);
        else
            CND4_pair(d1, d2, cnd1, cnd2);
#else
        CND4_pair(d1, d2, cnd1, cnd2);
#endif
        const v4sf value = S * cnd1 - X * discount * cnd2;
        std::memcpy(result + i, &value, sizeof(value));
    }

    if (i < last) {
        black_scholes_serial(a + i, a + n + i, a + 2 * n + i,
                             a + 3 * n + i, a + 4 * n + i, result + i, last - i);
    }
#else
    black_scholes_serial(a + first, a + n + first, a + 2 * n + first,
                         a + 3 * n + first, a + 4 * n + first,
                         result + first, last - first);
#endif
}

static inline void black_scholes_range(float* a, float* result, int n, int first, int last) {
    black_scholes_range_impl<false>(a, result, n, first, last);
}

extern "C" void run(const void* input1, const void* input2, void* output, int n, int parameter, int threads) {
    if (n <= 0)
        return;

    float* a = (float*)input1;
    float* result = (float*)output;

    if (threads <= 1) {
#if defined(__GNUC__) && (defined(__x86_64__) || defined(__i386__))
        if (n > 32768) {
            black_scholes_simd_bc307(a, a + n, a + 2 * n, a + 3 * n, a + 4 * n, result, n);
            return;
        }
#endif
        if (threads == 1) {
#if defined(__GNUC__) && (defined(__x86_64__) || defined(__i386__))
            int i = 0;
            for (; n - i >= 32; i += 32) {
                black_scholes_32(a, a + n, a + 2 * n, a + 3 * n, a + 4 * n, result, i);
            }
            if (i < n) {
                black_scholes_serial(a + i, a + n + i, a + 2 * n + i,
                                     a + 3 * n + i, a + 4 * n + i,
                                     result + i, n - i);
            }
#else
            black_scholes_range(a, result, n, 0, n);
#endif
        } else {
            black_scholes_range(a, result, n, 0, n);
        }
        return;
    }

    const bool use_443 = threads >= 4 && n <= 32768;
    #pragma omp parallel num_threads(threads) shared(a, result, n, use_443)
    {
        const int team_size = omp_get_num_threads();
        const int tid = omp_get_thread_num();
        const int quotient = n / team_size;
        const int remainder = n % team_size;
        const int first = quotient * tid + std::min(tid, remainder);
        const int last = first + quotient + (tid < remainder ? 1 : 0);

        if (use_443)
            black_scholes_range_impl<true>(a, result, n, first, last);
        else
            black_scholes_range(a, result, n, first, last);
    }
}
