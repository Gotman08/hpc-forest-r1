/*
  Copyright (c) 2010-2023, Intel Corporation

  SPDX-License-Identifier: BSD-3-Clause
*/

#include <cstdint>
#include <cstring>
#include <cmath>
#include <algorithm>
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
    const long long pixelCount = static_cast<long long>(width) * static_cast<long long>(height);
    const int workerCount = threads > 0 ? threads : 1;

    #pragma omp parallel for schedule(static) num_threads(workerCount) if(workerCount > 1)
    for (long long pixel = 0; pixel < pixelCount; ++pixel) {
        int j = static_cast<int>(pixel / width);
        int i = static_cast<int>(pixel % width);

        float x = x0 + i * dx;
        float y = y0 + j * dy;

        output[pixel] = mandel(x, y, maxIterations);
    }
}

extern "C" void run(const void* input1, const void* input2, void* output, int n, int parameter, int threads) {
    const float* a = static_cast<const float*>(input1);
    mandelbrot_serial(a[0], a[1], a[2], a[3], n * 3 / 2, n, parameter, static_cast<int*>(output), threads);
}
