/*
  Copyright (c) 2010-2023, Intel Corporation

  SPDX-License-Identifier: BSD-3-Clause
*/

#include <cstdint>
#include <cstring>
#include <cmath>
#include <algorithm>
#include <omp.h>

static void mandelbrot_row(float x0, float y, float dx, int width, int maxIterations, int j, int output[]) {
    enum { lane_count = 2 };

    for (int base = 0; base < width; ) {
        int remaining = width - base;
        int valid = remaining < lane_count ? remaining : lane_count;
        float c_re[lane_count];
        float z_re[lane_count];
        float z_im[lane_count];
        int active[lane_count];
        int counts[lane_count];

        for (int lane = 0; lane < lane_count; ++lane) {
            active[lane] = lane < valid;
            counts[lane] = 0;
            c_re[lane] = 0.0f;
            if (active[lane]) {
                int i = base + lane;
                c_re[lane] = x0 + i * dx;
            }
            z_re[lane] = c_re[lane];
            z_im[lane] = y;
        }

        for (int k = 0; k < maxIterations; ++k) {
            int any_active = 0;
            #pragma omp simd reduction(|:any_active)
            for (int lane = 0; lane < lane_count; ++lane) {
                if (active[lane]) {
                    if (z_re[lane] * z_re[lane] + z_im[lane] * z_im[lane] > 4.f) {
                        counts[lane] = k;
                        active[lane] = 0;
                    } else {
                        float new_re = z_re[lane] * z_re[lane] - z_im[lane] * z_im[lane];
                        float new_im = 2.f * z_re[lane] * z_im[lane];
                        z_re[lane] = c_re[lane] + new_re;
                        z_im[lane] = y + new_im;
                    }
                }
                any_active |= active[lane];
            }
            if (!any_active)
                break;
        }

        int final_count = maxIterations > 0 ? maxIterations : 0;
        for (int lane = 0; lane < lane_count; ++lane) {
            if (active[lane])
                counts[lane] = final_count;
            if (lane < valid) {
                int i = base + lane;
                output[j * width + i] = counts[lane];
            }
        }
        base += valid;
    }
}

static void mandelbrot_rows(float x0, float y0, float x1, float y1, int width, int height, int maxIterations, int threads, int output[]) {
    float dx = (x1 - x0) / width;
    float dy = (y1 - y0) / height;

    if (threads > 1) {
        #pragma omp parallel for schedule(dynamic, 8) num_threads(threads)
        for (int j = 0; j < height; ++j) {
            float y = y0 + j * dy;
            mandelbrot_row(x0, y, dx, width, maxIterations, j, output);
        }
    } else {
        for (int j = 0; j < height; ++j) {
            float y = y0 + j * dy;
            mandelbrot_row(x0, y, dx, width, maxIterations, j, output);
        }
    }
}

extern "C" void run(const void* input1, const void* input2, void* output, int n, int parameter, int threads)
{
    const float* a = (const float*)input1;
    mandelbrot_rows(a[0], a[1], a[2], a[3], n * 3 / 2, n, parameter, threads, (int*)output);
}
