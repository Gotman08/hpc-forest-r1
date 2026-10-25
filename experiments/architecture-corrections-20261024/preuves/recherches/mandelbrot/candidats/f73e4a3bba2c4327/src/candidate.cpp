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

void mandelbrot_serial(float x0, float y0, float x1, float y1, int width, int height, int maxIterations, int output[], int threads) {
    float dx = (x1 - x0) / width;
    float dy = (y1 - y0) / height;
    const int worker_count = threads > 1 ? threads : 1;

    #pragma omp parallel for schedule(dynamic, 2) num_threads(worker_count) if(threads > 1)
    for (int j = 0; j < height; j++) {
        float y = y0 + j * dy;
        int i = 0;

        for (; i + 1 < width; i += 2) {
            float c_re[2];
            float z_re[2];
            float z_im[2];
            int result[2];

            #pragma omp simd
            for (int lane = 0; lane < 2; ++lane) {
                int pixel = i + lane;
                c_re[lane] = x0 + pixel * dx;
                z_re[lane] = c_re[lane];
                z_im[lane] = y;
                result[lane] = maxIterations > 0 ? maxIterations : 0;
            }

            int any_active = 1;
            for (int iteration = 0; iteration < maxIterations && any_active; ++iteration) {
                #pragma omp simd
                for (int lane = 0; lane < 2; ++lane) {
                    if (result[lane] == maxIterations) {
                        if (z_re[lane] * z_re[lane] + z_im[lane] * z_im[lane] > 4.f) {
                            result[lane] = iteration;
                        } else {
                            float new_re = z_re[lane] * z_re[lane] - z_im[lane] * z_im[lane];
                            float new_im = 2.f * z_re[lane] * z_im[lane];
                            z_re[lane] = c_re[lane] + new_re;
                            z_im[lane] = y + new_im;
                        }
                    }
                }
                any_active = (result[0] == maxIterations) || (result[1] == maxIterations);
            }

            #pragma omp simd
            for (int lane = 0; lane < 2; ++lane) {
                int index = j * width + i + lane;
                output[index] = result[lane];
            }
        }

        for (; i < width; ++i) {
            float x = x0 + i * dx;
            int index = j * width + i;
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
{const float*a=(const float*)input1;mandelbrot_serial(a[0],a[1],a[2],a[3],n*3/2,n,parameter,(int*)output,threads);}
