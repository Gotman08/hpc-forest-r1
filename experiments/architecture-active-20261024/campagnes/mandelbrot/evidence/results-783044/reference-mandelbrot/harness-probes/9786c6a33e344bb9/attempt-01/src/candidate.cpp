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

static void mandel10(float x0, float y, float dx, int maxIterations,
                     int output[], int baseIndex, int first) {
#define INIT_PIXEL(K) \
    float c_re##K = x0 + (first + K) * dx; \
    float z_re##K = c_re##K; \
    float z_im##K = y; \
    int count##K = 0; \
    bool active##K = maxIterations > 0;

    INIT_PIXEL(0)
    INIT_PIXEL(1)
    INIT_PIXEL(2)
    INIT_PIXEL(3)
    INIT_PIXEL(4)
    INIT_PIXEL(5)
    INIT_PIXEL(6)
    INIT_PIXEL(7)
    INIT_PIXEL(8)
    INIT_PIXEL(9)

#define STEP_PIXEL(K) \
    if (active##K) { \
        if (z_re##K * z_re##K + z_im##K * z_im##K > 4.f) { \
            active##K = false; \
        } else { \
            float new_re = z_re##K * z_re##K - z_im##K * z_im##K; \
            float new_im = 2.f * z_re##K * z_im##K; \
            z_re##K = c_re##K + new_re; \
            z_im##K = y + new_im; \
            ++count##K; \
            if (count##K >= maxIterations) \
                active##K = false; \
        } \
    }

    while (active0 || active1 || active2 || active3 || active4 ||
           active5 || active6 || active7 || active8 || active9) {
        STEP_PIXEL(0)
        STEP_PIXEL(1)
        STEP_PIXEL(2)
        STEP_PIXEL(3)
        STEP_PIXEL(4)
        STEP_PIXEL(5)
        STEP_PIXEL(6)
        STEP_PIXEL(7)
        STEP_PIXEL(8)
        STEP_PIXEL(9)
    }

#undef STEP_PIXEL
#undef INIT_PIXEL

    output[baseIndex + (first + 0)] = count0;
    output[baseIndex + (first + 1)] = count1;
    output[baseIndex + (first + 2)] = count2;
    output[baseIndex + (first + 3)] = count3;
    output[baseIndex + (first + 4)] = count4;
    output[baseIndex + (first + 5)] = count5;
    output[baseIndex + (first + 6)] = count6;
    output[baseIndex + (first + 7)] = count7;
    output[baseIndex + (first + 8)] = count8;
    output[baseIndex + (first + 9)] = count9;
}

void mandelbrot_serial(float x0, float y0, float x1, float y1, int width,
                       int height, int maxIterations, int output[]) {
    float dx = (x1 - x0) / width;
    float dy = (y1 - y0) / height;

    for (int j = 0; j < height; j++) {
        float y = y0 + j * dy;
        int i = 0;
        for (; i <= width - 10; i += 10) {
            mandel10(x0, y, dx, maxIterations, output, j * width, i);
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
