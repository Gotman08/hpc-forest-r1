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

    for (int j = 0; j < height; j++) {
        for (int i = 0; i < width; ++i) {
            float x = x0 + i * dx;
            float y = y0 + j * dy;

            int index = (j * width + i);
            output[index] = mandel(x, y, maxIterations);
        }
    }
}

#define INIT_LANE(L, OFFSET) float c_re##L = x0 + (i + OFFSET) * dx; float z_re##L = c_re##L; float z_im##L = c_im; int iterations##L = 0; bool active##L = true
#define UPDATE_LANE(L) do { if (active##L) { if (z_re##L * z_re##L + z_im##L * z_im##L > 4.f) { active##L = false; } else { float new_re##L = z_re##L * z_re##L - z_im##L * z_im##L; float new_im##L = 2.f * z_re##L * z_im##L; z_re##L = c_re##L + new_re##L; z_im##L = c_im + new_im##L; ++iterations##L; } } } while (false)
#define STORE_LANE(L, OFFSET) output[j * width + (i + OFFSET)] = iterations##L

static void mandelbrot_interleaved16(float x0, float y0, float x1, float y1, int width, int height, int maxIterations, int output[]) {
    float dx = (x1 - x0) / width;
    float dy = (y1 - y0) / height;

    for (int j = 0; j < height; ++j) {
        float c_im = y0 + j * dy;
        int i = 0;
        for (; width - i >= 16; i += 16) {
            INIT_LANE(0, 0);
            INIT_LANE(1, 1);
            INIT_LANE(2, 2);
            INIT_LANE(3, 3);
            INIT_LANE(4, 4);
            INIT_LANE(5, 5);
            INIT_LANE(6, 6);
            INIT_LANE(7, 7);
            INIT_LANE(8, 8);
            INIT_LANE(9, 9);
            INIT_LANE(10, 10);
            INIT_LANE(11, 11);
            INIT_LANE(12, 12);
            INIT_LANE(13, 13);
            INIT_LANE(14, 14);
            INIT_LANE(15, 15);

            for (int k = 0; k < maxIterations; ++k) {
                UPDATE_LANE(0);
                UPDATE_LANE(1);
                UPDATE_LANE(2);
                UPDATE_LANE(3);
                UPDATE_LANE(4);
                UPDATE_LANE(5);
                UPDATE_LANE(6);
                UPDATE_LANE(7);
                UPDATE_LANE(8);
                UPDATE_LANE(9);
                UPDATE_LANE(10);
                UPDATE_LANE(11);
                UPDATE_LANE(12);
                UPDATE_LANE(13);
                UPDATE_LANE(14);
                UPDATE_LANE(15);
            }

            STORE_LANE(0, 0);
            STORE_LANE(1, 1);
            STORE_LANE(2, 2);
            STORE_LANE(3, 3);
            STORE_LANE(4, 4);
            STORE_LANE(5, 5);
            STORE_LANE(6, 6);
            STORE_LANE(7, 7);
            STORE_LANE(8, 8);
            STORE_LANE(9, 9);
            STORE_LANE(10, 10);
            STORE_LANE(11, 11);
            STORE_LANE(12, 12);
            STORE_LANE(13, 13);
            STORE_LANE(14, 14);
            STORE_LANE(15, 15);
        }

        for (; i < width; ++i) {
            float x = x0 + i * dx;
            float y = y0 + j * dy;
            output[j * width + i] = mandel(x, y, maxIterations);
        }
    }
}

#undef INIT_LANE
#undef UPDATE_LANE
#undef STORE_LANE

#include <cstdint>
#include <cstring>
#include <cmath>
#include <algorithm>
#include <omp.h>
extern "C" void run(const void* input1,const void* input2,void* output,int n,int parameter,int threads)
{const float*a=(const float*)input1;mandelbrot_interleaved16(a[0],a[1],a[2],a[3],n*3/2,n,parameter,(int*)output);}
