/*
  Copyright (c) 2010-2023, Intel Corporation

  SPDX-License-Identifier: BSD-3-Clause
*/

static int mandel(float c_re, float c_im, int count) {
    float z_re = c_re, z_im = c_im;

    if (count <= 0)
        return count;

    if (z_re * z_re + z_im * z_im > 4.f)
        return 0;

    // If both components of c are at most 1/8 in magnitude, induction keeps
    // both components of every float iterate at most 1/4 in magnitude:
    // each square-product is at most 1/16, so each component of z*z is at
    // most 1/8, and adding c stays within 1/4. Thus the escape norm is at
    // most 1/8, safely below 4, for every iteration count.
    if (c_re >= -0.125f && c_re <= 0.125f &&
        c_im >= -0.125f && c_im <= 0.125f)
        return count;

    for (int i = 1; i < count; ++i) {
        float new_re = z_re * z_re - z_im * z_im;
        float new_im = 2.f * z_re * z_im;
        float next_re = c_re + new_re;
        float next_im = c_im + new_im;

        z_re = next_re;
        z_im = next_im;
        if (z_re * z_re + z_im * z_im > 4.f)
            return i;
    }

    return count;
}

void mandelbrot_serial(float x0, float y0, float x1, float y1, int width, int height, int maxIterations, int output[]) {
    float dx = (x1 - x0) / width;
    float dy = (y1 - y0) / height;

    for (int j = 0; j < height; j++) {
        for (int i = 0; i < width; ++i) {
            float x = x0 + i * dx;
            float y = y0 + j * dy;

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
