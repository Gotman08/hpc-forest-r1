/*
  Copyright (c) 2010-2023, Intel Corporation

  SPDX-License-Identifier: BSD-3-Clause
*/

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
                           int width, int maxIterations, int j, int output[]) {
    for (int i = 0; i < width; ++i) {
        float x = x0 + i * dx;
        float y = y0 + j * dy;

        int index = (j * width + i);
        output[index] = mandel(x, y, maxIterations);
    }
}

static void mandelbrot_compute(float x0, float y0, float x1, float y1,
                               int width, int height, int maxIterations,
                               int threads, int output[]) {
    float dx = (x1 - x0) / width;
    float dy = (y1 - y0) / height;

    int teamSize = threads;
    if (teamSize > height)
        teamSize = height;

    if (teamSize <= 1) {
        for (int j = 0; j < height; ++j)
            mandelbrot_row(x0, y0, dx, dy, width, maxIterations, j, output);
        return;
    }

    #pragma omp parallel for schedule(dynamic, 4) num_threads(teamSize)
    for (int j = 0; j < height; ++j)
        mandelbrot_row(x0, y0, dx, dy, width, maxIterations, j, output);
}

#include <cstdint>
#include <cstring>
#include <cmath>
#include <algorithm>
#include <omp.h>
extern "C" void run(const void* input1,const void* input2,void* output,int n,int parameter,int threads)
{
    const float* a = (const float*)input1;
    mandelbrot_compute(a[0], a[1], a[2], a[3], n * 3 / 2, n, parameter,
                       threads, (int*)output);
}
