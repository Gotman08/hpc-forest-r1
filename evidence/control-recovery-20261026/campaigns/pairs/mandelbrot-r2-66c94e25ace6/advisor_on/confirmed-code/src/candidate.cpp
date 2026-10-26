/*
  Copyright (c) 2010-2023, Intel Corporation

  SPDX-License-Identifier: BSD-3-Clause
*/

#include <cstdint>
#include <cstring>
#include <cmath>
#include <algorithm>
#include <omp.h>

#if defined(_OPENMP) && _OPENMP >= 201307
#define MANDELBROT_HAS_OMP_SIMD 1
#endif

static int mandel(float c_re, float c_im, int count) {
    float z_re = c_re, z_im = c_im;
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
}

static void mandelbrot_row(float x0, float y0, float dx, float dy,
                           int width, int j, int maxIterations, int output[]) {
    enum { SIMD_PIXELS = 8 };
    int i = 0;

#ifdef MANDELBROT_HAS_OMP_SIMD
    for (; i + SIMD_PIXELS <= width; i += SIMD_PIXELS) {
        float c_re[SIMD_PIXELS];
        float c_im[SIMD_PIXELS];
        float z_re[SIMD_PIXELS];
        float z_im[SIMD_PIXELS];
        int iterations[SIMD_PIXELS];
        unsigned char active[SIMD_PIXELS];
        int active_count = maxIterations > 0 ? SIMD_PIXELS : 0;

        for (int lane = 0; lane < SIMD_PIXELS; ++lane) {
            const int pixel = i + lane;
            c_re[lane] = x0 + pixel * dx;
            c_im[lane] = y0 + j * dy;
            z_re[lane] = c_re[lane];
            z_im[lane] = c_im[lane];
            iterations[lane] = maxIterations > 0 ? maxIterations : 0;
            active[lane] = maxIterations > 0;
        }

        for (int iter = 0; iter < maxIterations && active_count > 0; ++iter) {
            int escaped = 0;
#pragma omp simd reduction(+:escaped)
            for (int lane = 0; lane < SIMD_PIXELS; ++lane) {
                if (active[lane]) {
                    if (z_re[lane] * z_re[lane] + z_im[lane] * z_im[lane] > 4.f) {
                        iterations[lane] = iter;
                        active[lane] = 0;
                        escaped += 1;
                    } else {
                        float new_re = z_re[lane] * z_re[lane] - z_im[lane] * z_im[lane];
                        float new_im = 2.f * z_re[lane] * z_im[lane];
                        z_re[lane] = c_re[lane] + new_re;
                        z_im[lane] = c_im[lane] + new_im;
                    }
                }
            }

            active_count -= escaped;
            if (active_count == 0)
                break;

            if (active_count == 1) {
                int lane = 0;
                while (lane < SIMD_PIXELS && !active[lane])
                    ++lane;

                if (lane < SIMD_PIXELS) {
                    for (int tail_iter = iter + 1; tail_iter < maxIterations; ++tail_iter) {
                        if (z_re[lane] * z_re[lane] + z_im[lane] * z_im[lane] > 4.f) {
                            iterations[lane] = tail_iter;
                            break;
                        }

                        float new_re = z_re[lane] * z_re[lane] - z_im[lane] * z_im[lane];
                        float new_im = 2.f * z_re[lane] * z_im[lane];
                        z_re[lane] = c_re[lane] + new_re;
                        z_im[lane] = c_im[lane] + new_im;
                    }
                }
                break;
            }
        }

        for (int lane = 0; lane < SIMD_PIXELS; ++lane) {
            const int pixel = i + lane;
            output[j * width + pixel] = iterations[lane];
        }
    }
#endif

    for (; i < width; ++i) {
        float x = x0 + i * dx;
        float y = y0 + j * dy;
        output[j * width + i] = mandel(x, y, maxIterations);
    }
}

static void mandelbrot_compute(float x0, float y0, float x1, float y1,
                               int width, int height, int maxIterations,
                               int output[], int threads) {
    float dx = (x1 - x0) / width;
    float dy = (y1 - y0) / height;

#if defined(_OPENMP)
    if (threads > 1) {
        std::int64_t next_row = 0;
#pragma omp parallel num_threads(threads) shared(next_row)
        {
            for (;;) {
                std::int64_t first_row;
#pragma omp atomic capture
                {
                    first_row = next_row;
                    next_row += 4;
                }
                if (first_row >= height)
                    break;

                const int row_begin = static_cast<int>(first_row);
                const int row_end = static_cast<int>(
                    std::min<std::int64_t>(first_row + 4, height));
                for (int j = row_begin; j < row_end; ++j)
                    mandelbrot_row(x0, y0, dx, dy, width, j, maxIterations, output);
            }
        }
        return;
    }
#endif

    for (int j = 0; j < height; ++j)
        mandelbrot_row(x0, y0, dx, dy, width, j, maxIterations, output);
}

extern "C" void run(const void* input1, const void* input2, void* output,
                    int n, int parameter, int threads) {
    const float* a = (const float*)input1;
    mandelbrot_compute(a[0], a[1], a[2], a[3], n * 3 / 2, n,
                       parameter, (int*)output, threads);
}
