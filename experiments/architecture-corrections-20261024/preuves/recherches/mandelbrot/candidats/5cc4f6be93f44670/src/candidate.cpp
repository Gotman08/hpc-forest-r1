/*
  Copyright (c) 2010-2023, Intel Corporation

  SPDX-License-Identifier: BSD-3-Clause
*/

#include <omp.h>

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

void mandelbrot_serial(float x0, float y0, float x1, float y1, int width, int height, int maxIterations, int output[], int threads) {
    float dx = (x1 - x0) / width;
    float dy = (y1 - y0) / height;

    const long long row_count =
        (width > 0 && height > 0)
            ? static_cast<long long>(height)
            : 0;
    const int worker_count = threads > 1 ? threads : 1;

    #pragma omp parallel for schedule(guided, 1) num_threads(worker_count) if(worker_count > 1)
    for (long long row = 0; row < row_count; ++row) {
        const int j = static_cast<int>(row);
        for (int i = 0; i < width; ++i) {
            float x = x0 + i * dx;
            float y = y0 + j * dy;

            output[row * width + i] = mandel(x, y, maxIterations);
        }
    }
}

extern "C" void run(const void* input1, const void* input2, void* output, int n, int parameter, int threads)
{
    const float* a = (const float*)input1;
    mandelbrot_serial(a[0], a[1], a[2], a[3], n * 3 / 2, n, parameter, (int*)output, threads);
}
