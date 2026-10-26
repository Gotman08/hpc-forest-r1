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

static const int kSimdLanes = 8;

static void mandel_simd_block(const float c_re[], const float c_im[], int count, int results[]) {
    float z_re[kSimdLanes];
    float z_im[kSimdLanes];
    int active[kSimdLanes];

    for (int lane = 0; lane < kSimdLanes; ++lane) {
        z_re[lane] = c_re[lane];
        z_im[lane] = c_im[lane];
        active[lane] = 1;
        results[lane] = 0;
    }

    for (int i = 0; i < count; ++i) {
        int any_active = 0;
#pragma omp simd reduction(|:any_active)
        for (int lane = 0; lane < kSimdLanes; ++lane) {
            if (active[lane]) {
                if (z_re[lane] * z_re[lane] + z_im[lane] * z_im[lane] > 4.f) {
                    active[lane] = 0;
                } else {
                    float new_re = z_re[lane] * z_re[lane] - z_im[lane] * z_im[lane];
                    float new_im = 2.f * z_re[lane] * z_im[lane];
                    z_re[lane] = c_re[lane] + new_re;
                    z_im[lane] = c_im[lane] + new_im;
                    results[lane] = i + 1;
                }
            }
            any_active |= active[lane];
        }
        if (!any_active)
            break;
    }
}

void mandelbrot_serial(float x0, float y0, float x1, float y1, int width, int height, int maxIterations, int output[], int threads) {
    float dx = (x1 - x0) / width;
    float dy = (y1 - y0) / height;
    const int thread_count = threads > 0 ? threads : 1;

#pragma omp parallel for schedule(dynamic, 1) num_threads(thread_count)
    for (int row = 0; row < height; ++row) {
        int column = 0;
        float c_re[kSimdLanes];
        float c_im[kSimdLanes];
        int counts[kSimdLanes];

        for (; column <= width - kSimdLanes; column += kSimdLanes) {
            for (int lane = 0; lane < kSimdLanes; ++lane) {
                c_re[lane] = x0 + (column + lane) * dx;
                c_im[lane] = y0 + row * dy;
            }

            mandel_simd_block(c_re, c_im, maxIterations, counts);
            for (int lane = 0; lane < kSimdLanes; ++lane)
                output[row * width + column + lane] = counts[lane];
        }

        for (; column < width; ++column) {
            float x = x0 + column * dx;
            float y = y0 + row * dy;
            output[row * width + column] = mandel(x, y, maxIterations);
        }
    }
}
#include <cstdint>
#include <cstring>
#include <cmath>
#include <algorithm>
#include <omp.h>
extern "C" void run(const void* input1,const void* input2,void* output,int n,int parameter,int threads)
{const float*a=(const float*)input1;mandelbrot_serial(a[0],a[1],a[2],a[3],n*3/2,n,parameter,(int*)output,threads);}
