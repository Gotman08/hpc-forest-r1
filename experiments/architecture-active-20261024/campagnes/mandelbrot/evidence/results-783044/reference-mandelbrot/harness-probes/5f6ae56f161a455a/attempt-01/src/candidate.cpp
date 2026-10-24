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

static void mandel_group2(float c_re0, float c_im0,
                          float c_re1, float c_im1,
                          int count, int* output) {
    float z_re0 = c_re0, z_im0 = c_im0;
    float z_re1 = c_re1, z_im1 = c_im1;
    int active0 = 1, active1 = 1;
    int initial_result = count > 0 ? count : 0;
    output[0] = initial_result;
    output[1] = initial_result;

    for (int i = 0; i < count && (active0 || active1); ++i) {
        if (active0) {
            if (z_re0 * z_re0 + z_im0 * z_im0 > 4.f) {
                output[0] = i;
                active0 = 0;
            } else {
                float new_re0 = z_re0 * z_re0 - z_im0 * z_im0;
                float new_im0 = 2.f * z_re0 * z_im0;
                z_re0 = c_re0 + new_re0;
                z_im0 = c_im0 + new_im0;
            }
        }
        if (active1) {
            if (z_re1 * z_re1 + z_im1 * z_im1 > 4.f) {
                output[1] = i;
                active1 = 0;
            } else {
                float new_re1 = z_re1 * z_re1 - z_im1 * z_im1;
                float new_im1 = 2.f * z_re1 * z_im1;
                z_re1 = c_re1 + new_re1;
                z_im1 = c_im1 + new_im1;
            }
        }
    }
}

void mandelbrot_serial(float x0, float y0, float x1, float y1, int width, int height, int maxIterations, int output[]) {
    float dx = (x1 - x0) / width;
    float dy = (y1 - y0) / height;

    for (int j = 0; j < height; j++) {
        float y = y0 + j * dy;
        int i = 0;
        for (; i < width && width - i >= 2; i += 2) {
            float x0_group = x0 + i * dx;
            float x1_group = x0 + (i + 1) * dx;
            int index = j * width + i;
            mandel_group2(x0_group, y, x1_group, y, maxIterations, output + index);
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
