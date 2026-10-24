/*
  Copyright (c) 2010-2023, Intel Corporation

  SPDX-License-Identifier: BSD-3-Clause
*/

#include <algorithm>
#include <omp.h>

static void mandelbrot_row(float x0, float y0, float dx, float dy,
                           int j, int width, int maxIterations, int output[]) {
    constexpr int blockWidth = 128;

    for (int base = 0; base < width;) {
        const int lanes = std::min(blockWidth, width - base);
        float c_re[blockWidth];
        float c_im[blockWidth];
        float z_re[blockWidth];
        float z_im[blockWidth];
        int result[blockWidth];

        #pragma omp simd
        for (int lane = 0; lane < lanes; ++lane) {
            const int i = base + lane;
            c_re[lane] = x0 + i * dx;
            c_im[lane] = y0 + j * dy;
            z_re[lane] = c_re[lane];
            z_im[lane] = c_im[lane];
            result[lane] = maxIterations > 0 ? maxIterations : 0;
        }

        for (int iteration = 0; iteration < maxIterations; ++iteration) {
            int any_active = 0;
            #pragma omp simd reduction(|:any_active)
            for (int lane = 0; lane < lanes; ++lane) {
                if (result[lane] == maxIterations) {
                    if (z_re[lane] * z_re[lane] + z_im[lane] * z_im[lane] > 4.f) {
                        result[lane] = iteration;
                    } else {
                        float new_re = z_re[lane] * z_re[lane] - z_im[lane] * z_im[lane];
                        float new_im = 2.f * z_re[lane] * z_im[lane];
                        z_re[lane] = c_re[lane] + new_re;
                        z_im[lane] = c_im[lane] + new_im;
                        any_active = 1;
                    }
                }
            }
            if (!any_active)
                break;
        }

        #pragma omp simd
        for (int lane = 0; lane < lanes; ++lane) {
            const int i = base + lane;
            output[j * width + i] = result[lane];
        }

        base += lanes;
    }
}

static void mandelbrot_serial(float x0, float y0, float x1, float y1,
                              int width, int height, int maxIterations,
                              int output[], int threads) {
    if (width <= 0 || height <= 0)
        return;

    const float dx = (x1 - x0) / width;
    const float dy = (y1 - y0) / height;
    const int requestedThreads = std::max(1, threads);
    const int teamSize = std::min(requestedThreads, height);

    if (teamSize > 1) {
        #pragma omp parallel for schedule(dynamic, 1) num_threads(teamSize)
        for (int j = 0; j < height; ++j)
            mandelbrot_row(x0, y0, dx, dy, j, width, maxIterations, output);
    } else {
        for (int j = 0; j < height; ++j)
            mandelbrot_row(x0, y0, dx, dy, j, width, maxIterations, output);
    }
}

extern "C" void run(const void* input1, const void* input2, void* output,
                     int n, int parameter, int threads) {
    (void)input2;
    const float* a = static_cast<const float*>(input1);
    mandelbrot_serial(a[0], a[1], a[2], a[3], n * 3 / 2, n,
                      parameter, static_cast<int*>(output), threads);
}
