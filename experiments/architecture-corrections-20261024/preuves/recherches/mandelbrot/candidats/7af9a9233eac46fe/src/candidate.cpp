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

static void mandel_eight(const float c_re[8], const float c_im[8], int count, int result[8]) {
    float z_re[8], z_im[8];
    int active[8];
    const int limit = count > 0 ? count : 0;

    #pragma omp simd
    for (int lane = 0; lane < 8; ++lane) {
        z_re[lane] = c_re[lane];
        z_im[lane] = c_im[lane];
        active[lane] = 1;
        result[lane] = limit;
    }

    int active_lanes = 8;
    for (int iter = 0; iter < limit && active_lanes != 0; ++iter) {
        int escaped_lanes = 0;
        #pragma omp simd reduction(+:escaped_lanes)
        for (int lane = 0; lane < 8; ++lane) {
            if (active[lane]) {
                if (z_re[lane] * z_re[lane] + z_im[lane] * z_im[lane] > 4.f) {
                    result[lane] = iter;
                    active[lane] = 0;
                    escaped_lanes += 1;
                } else {
                    float new_re = z_re[lane] * z_re[lane] - z_im[lane] * z_im[lane];
                    float new_im = 2.f * z_re[lane] * z_im[lane];
                    z_re[lane] = c_re[lane] + new_re;
                    z_im[lane] = c_im[lane] + new_im;
                }
            }
        }
        active_lanes -= escaped_lanes;
    }
}

void mandelbrot_serial(float x0, float y0, float x1, float y1, int width, int height, int maxIterations, int output[]) {
    float dx = (x1 - x0) / width;
    float dy = (y1 - y0) / height;

    for (int j = 0; j < height; j++) {
        float y = y0 + j * dy;
        int i = 0;
        if (width >= 8) {
            for (; i <= width - 8; i += 8) {
                float c_re[8], c_im[8];
                int result[8];

                #pragma omp simd
                for (int lane = 0; lane < 8; ++lane) {
                    int pixel = i + lane;
                    c_re[lane] = x0 + pixel * dx;
                    c_im[lane] = y;
                }

                mandel_eight(c_re, c_im, maxIterations, result);

                #pragma omp simd
                for (int lane = 0; lane < 8; ++lane) {
                    int index = j * width + i + lane;
                    output[index] = result[lane];
                }
            }
        }
        for (; i < width; ++i) {
            float x = x0 + i * dx;
            int index = (j * width + i);
            output[index] = mandel(x, y, maxIterations);
        }
    }
}
#include <cstdint>
#include <cstring>
#include <cmath>
#include <algorithm>
#include <omp.h>
extern "C" void run(const void* input1,const void* input2,void* output,int n,int parameter,int threads)
{const float*a=(const float*)input1;mandelbrot_serial(a[0],a[1],a[2],a[3],n*3/2,n,parameter,(int*)output);}
