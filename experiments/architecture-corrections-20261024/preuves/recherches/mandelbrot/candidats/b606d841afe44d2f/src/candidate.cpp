/*
  Copyright (c) 2010-2023, Intel Corporation

  SPDX-License-Identifier: BSD-3-Clause
*/

#include <cstddef>
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

void mandelbrot_flat_dynamic(float x0, float y0, float x1, float y1,
                             int width, int height, int maxIterations,
                             int threads, int output[]) {
    if (width <= 0 || height <= 0)
        return;

    float dx = (x1 - x0) / width;
    float dy = (y1 - y0) / height;
    const long long pixel_count =
        static_cast<long long>(width) * static_cast<long long>(height);
    const int worker_count = threads > 1 ? threads : 1;
    const int chunk_pixels = width > 1 ? width / 2 : 1;

    #pragma omp parallel for schedule(dynamic, chunk_pixels) num_threads(worker_count) if (worker_count > 1)
    for (long long pixel = 0; pixel < pixel_count; ++pixel) {
        const int j = static_cast<int>(pixel / width);
        const int i = static_cast<int>(pixel % width);

        float x = x0 + i * dx;
        float y = y0 + j * dy;

        const std::size_t index =
            static_cast<std::size_t>(j) * static_cast<std::size_t>(width) +
            static_cast<std::size_t>(i);
        output[index] = mandel(x, y, maxIterations);
    }
}

extern "C" void run(const void* input1, const void* input2, void* output,
                    int n, int parameter, int threads) {
    const float* a = static_cast<const float*>(input1);
    mandelbrot_flat_dynamic(a[0], a[1], a[2], a[3], n * 3 / 2, n,
                            parameter, threads, static_cast<int*>(output));
}
