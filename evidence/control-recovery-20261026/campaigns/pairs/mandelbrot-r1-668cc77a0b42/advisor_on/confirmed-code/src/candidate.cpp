/*
  Copyright (c) 2010-2023, Intel Corporation

  SPDX-License-Identifier: BSD-3-Clause
*/

#include <cmath>
#include <cfloat>
#include <cstdint>
#include <cstring>
#include <limits>
#include <omp.h>

#ifndef MANDELBROT_USE_CERTIFICATE
#define MANDELBROT_USE_CERTIFICATE 1
#endif

#ifndef MANDELBROT_USE_CYCLE
#define MANDELBROT_USE_CYCLE 1
#endif

#if defined(__FAST_MATH__)
#define MANDELBROT_WIDE_FP_BUILD 0
#elif defined(__FINITE_MATH_ONLY__) && __FINITE_MATH_ONLY__ > 0
#define MANDELBROT_WIDE_FP_BUILD 0
#elif defined(FLT_EVAL_METHOD) && FLT_EVAL_METHOD == 0
#define MANDELBROT_WIDE_FP_BUILD 1
#else
#define MANDELBROT_WIDE_FP_BUILD 0
#endif

#if MANDELBROT_USE_CERTIFICATE
#if MANDELBROT_WIDE_FP_BUILD
static inline bool wide_certificate_fp_supported() {
    return std::numeric_limits<float>::is_iec559 &&
           std::numeric_limits<float>::radix == 2 &&
           std::numeric_limits<float>::digits == 24 &&
           std::numeric_limits<float>::min_exponent == -125 &&
           std::numeric_limits<float>::max_exponent == 128 &&
           std::numeric_limits<float>::has_denorm == std::denorm_present;
}
#endif

/*
  For binary32 operations with intermediates below 1, use the conservative
  absolute per-operation error E = 2^-23 + 2^-120. The first term bounds a
  full ulp for IEEE rounding directions; the second dominates underflow-scale
  errors for these bounded operands. The real update has at most four rounded
  operations and the imaginary update at most three, so the vector error is
  at most 5E. Starting with |z0| <= sqrt(2)/8, if |z| <= 1/4 then
  |z_next| <= sqrt(2)/8 + 1/16 + 5E < 1/4. Thus the rounded recurrence cannot
  escape for coordinates in the widened square. The test is on the computed
  float coordinates, not on assumed grid alignment.
*/
static inline bool certified_nonescaping(float c_re, float c_im) {
#if MANDELBROT_WIDE_FP_BUILD
    const float wide_limit = 1.0f / 8.0f;
    if (wide_certificate_fp_supported() &&
        c_re >= -wide_limit && c_re <= wide_limit &&
        c_im >= -wide_limit && c_im <= wide_limit)
        return true;
#endif

    const float limit = 1.0f / 64.0f;
    return c_re >= -limit && c_re <= limit &&
           c_im >= -limit && c_im <= limit;
}
#endif

#if MANDELBROT_USE_CYCLE
static inline bool same_state(float a_re, float a_im,
                              float b_re, float b_im) {
    return std::memcmp(&a_re, &b_re, sizeof(float)) == 0 &&
           std::memcmp(&a_im, &b_im, sizeof(float)) == 0;
}
#endif

static int mandel(float c_re, float c_im, int count) {
    if (count <= 0)
        return 0;

#if MANDELBROT_USE_CERTIFICATE
    if (certified_nonescaping(c_re, c_im))
        return count;
#endif

    float z_re = c_re, z_im = c_im;
#if MANDELBROT_USE_CYCLE
    // Let short escaping orbits use the unchanged recurrence without cycle
    // bookkeeping. Seed Brent from the exact state reached after the warmup.
    const int cycle_warmup = 8;
    int i = 0;
    for (; i < count && i < cycle_warmup; ++i) {
        if (z_re * z_re + z_im * z_im > 4.f)
            break;

        float new_re = z_re * z_re - z_im * z_im;
        float new_im = 2.f * z_re * z_im;
        z_re = c_re + new_re;
        z_im = c_im + new_im;
    }

    if (i == cycle_warmup && i < count) {
        float checkpoint_re = z_re, checkpoint_im = z_im;
        std::uint64_t power = 1, length = 0;
        bool track_cycle = std::isfinite(c_re) && std::isfinite(c_im) &&
                           std::isfinite(z_re) && std::isfinite(z_im);

        for (; i < count; ++i) {
            if (z_re * z_re + z_im * z_im > 4.f)
                break;

            if (track_cycle && (!std::isfinite(z_re) || !std::isfinite(z_im)))
                track_cycle = false;

            float new_re = z_re * z_re - z_im * z_im;
            float new_im = 2.f * z_re * z_im;
            z_re = c_re + new_re;
            z_im = c_im + new_im;

            if (track_cycle) {
                if (!std::isfinite(z_re) || !std::isfinite(z_im)) {
                    track_cycle = false;
                } else if (same_state(z_re, z_im, checkpoint_re, checkpoint_im)) {
                    return count;
                } else {
                    ++length;
                    if (length == power) {
                        checkpoint_re = z_re;
                        checkpoint_im = z_im;
                        power *= 2;
                        length = 0;
                    }
                }
            }
        }
    }

    return i;
#else
    int i;
    for (i = 0; i < count; ++i) {
        if (z_re * z_re + z_im * z_im > 4.f)
            break;

        float new_re = z_re * z_re - z_im * z_im;
        float new_im = 2.f * z_re * z_im;
        z_re = c_re + new_re;
        z_im = c_im + new_im;
    }

    return i;
#endif
}

static void mandelbrot_rows(float x0, float y0, float x1, float y1,
                            int width, int height, int maxIterations,
                            int threads, int output[]) {
    float dx = (x1 - x0) / width;
    float dy = (y1 - y0) / height;
    const int thread_count = threads > 0 ? threads : 1;

    #pragma omp parallel for schedule(dynamic, 2) num_threads(thread_count) if(thread_count > 1)
    for (int j = 0; j < height; ++j) {
        for (int i = 0; i < width; ++i) {
            float x = x0 + i * dx;
            float y = y0 + j * dy;
            int index = j * width + i;
            output[index] = mandel(x, y, maxIterations);
        }
    }
}

extern "C" void run(const void* input1, const void* input2, void* output,
                     int n, int parameter, int threads) {
    const float* a = static_cast<const float*>(input1);
    const int width = n * 3 / 2;
    const int height = n;
    mandelbrot_rows(a[0], a[1], a[2], a[3], width, height, parameter,
                    threads, static_cast<int*>(output));
}
