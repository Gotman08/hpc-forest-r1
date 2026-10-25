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

void mandelbrot_serial(float x0, float y0, float x1, float y1, int width, int height, int maxIterations, int output[]) {
    float dx = (x1 - x0) / width;
    float dy = (y1 - y0) / height;
    const int vector_end = width - width % 4;

    for (int j = 0; j < height; j++) {
        for (int i = 0; i < vector_end; i += 4) {
            float c_re[4];
            float c_im[4];
            float z_re[4];
            float z_im[4];
            int active[4] = {1, 1, 1, 1};
            int result[4];

            #pragma omp simd
            for (int lane = 0; lane < 4; ++lane) {
                int pixel = i + lane;
                c_re[lane] = x0 + pixel * dx;
                c_im[lane] = y0 + j * dy;
                z_re[lane] = c_re[lane];
                z_im[lane] = c_im[lane];
                result[lane] = maxIterations > 0 ? maxIterations : 0;
            }

            for (int k = 0; k < maxIterations; ++k) {
                #pragma omp simd
                for (int lane = 0; lane < 4; ++lane) {
                    if (active[lane]) {
                        if (z_re[lane] * z_re[lane] + z_im[lane] * z_im[lane] > 4.f) {
                            active[lane] = 0;
                            result[lane] = k;
                        } else {
                            float new_re = z_re[lane] * z_re[lane] - z_im[lane] * z_im[lane];
                            float new_im = 2.f * z_re[lane] * z_im[lane];
                            z_re[lane] = c_re[lane] + new_re;
                            z_im[lane] = c_im[lane] + new_im;
                        }
                    }
                }

                if (!(active[0] || active[1] || active[2] || active[3]))
                    break;
            }

            #pragma omp simd
            for (int lane = 0; lane < 4; ++lane) {
                int pixel = i + lane;
                int index = j * width + pixel;
                output[index] = result[lane];
            }
        }

        for (int i = vector_end; i < width; ++i) {
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
