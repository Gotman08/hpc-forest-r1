/*
  Copyright (c) 2010-2023, Intel Corporation

  SPDX-License-Identifier: BSD-3-Clause
*/

static int mandel(float c_re, float c_im, int count) {
    if (count <= 0)
        return count;

    float z_re = c_re, z_im = c_im;
    if (z_re * z_re + z_im * z_im > 4.f)
        return 0;

    float older_re = z_re, older_im = z_im;
    for (int i = 1; i < count; ++i) {
        float previous_re = z_re, previous_im = z_im;
        float new_re = z_re * z_re - z_im * z_im;
        float new_im = 2.f * z_re * z_im;
        z_re = c_re + new_re;
        z_im = c_im + new_im;

        if (z_re * z_re + z_im * z_im > 4.f)
            return i;

        // After the escape check, a repeated one- or two-state orbit repeats
        // under the same finite-precision recurrence and cannot escape later.
        if ((z_re == previous_re && z_im == previous_im) ||
            (i > 1 && z_re == older_re && z_im == older_im))
            return count;

        older_re = previous_re;
        older_im = previous_im;
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
