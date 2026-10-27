/*
  Copyright (c) 2010-2023, Intel Corporation

  SPDX-License-Identifier: BSD-3-Clause
*/

#include <omp.h>

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

static inline void mandel_five(float c_re0, float c_im0,
                               float c_re1, float c_im1,
                               float c_re2, float c_im2,
                               float c_re3, float c_im3,
                               float c_re4, float c_im4,
                               int count, int result[5]) {
    float z_re0 = c_re0, z_im0 = c_im0;
    float z_re1 = c_re1, z_im1 = c_im1;
    float z_re2 = c_re2, z_im2 = c_im2;
    float z_re3 = c_re3, z_im3 = c_im3;
    float z_re4 = c_re4, z_im4 = c_im4;

    int result0 = count > 0 ? count : 0;
    int result1 = count > 0 ? count : 0;
    int result2 = count > 0 ? count : 0;
    int result3 = count > 0 ? count : 0;
    int result4 = count > 0 ? count : 0;
    bool active0 = count > 0;
    bool active1 = count > 0;
    bool active2 = count > 0;
    bool active3 = count > 0;
    bool active4 = count > 0;

    for (int k = 0; k < count && (active0 || active1 || active2 || active3 || active4); ++k) {
        if (active0) {
            if (z_re0 * z_re0 + z_im0 * z_im0 > 4.f) {
                result0 = k;
                active0 = false;
            } else {
                float new_re = z_re0 * z_re0 - z_im0 * z_im0;
                float new_im = 2.f * z_re0 * z_im0;
                z_re0 = c_re0 + new_re;
                z_im0 = c_im0 + new_im;
            }
        }
        if (active1) {
            if (z_re1 * z_re1 + z_im1 * z_im1 > 4.f) {
                result1 = k;
                active1 = false;
            } else {
                float new_re = z_re1 * z_re1 - z_im1 * z_im1;
                float new_im = 2.f * z_re1 * z_im1;
                z_re1 = c_re1 + new_re;
                z_im1 = c_im1 + new_im;
            }
        }
        if (active2) {
            if (z_re2 * z_re2 + z_im2 * z_im2 > 4.f) {
                result2 = k;
                active2 = false;
            } else {
                float new_re = z_re2 * z_re2 - z_im2 * z_im2;
                float new_im = 2.f * z_re2 * z_im2;
                z_re2 = c_re2 + new_re;
                z_im2 = c_im2 + new_im;
            }
        }
        if (active3) {
            if (z_re3 * z_re3 + z_im3 * z_im3 > 4.f) {
                result3 = k;
                active3 = false;
            } else {
                float new_re = z_re3 * z_re3 - z_im3 * z_im3;
                float new_im = 2.f * z_re3 * z_im3;
                z_re3 = c_re3 + new_re;
                z_im3 = c_im3 + new_im;
            }
        }
        if (active4) {
            if (z_re4 * z_re4 + z_im4 * z_im4 > 4.f) {
                result4 = k;
                active4 = false;
            } else {
                float new_re = z_re4 * z_re4 - z_im4 * z_im4;
                float new_im = 2.f * z_re4 * z_im4;
                z_re4 = c_re4 + new_re;
                z_im4 = c_im4 + new_im;
            }
        }
    }

    result[0] = result0;
    result[1] = result1;
    result[2] = result2;
    result[3] = result3;
    result[4] = result4;
}

static inline void mandelbrot_row(float x0, float y0, float dx, float dy,
                                  int width, int j, int maxIterations,
                                  int output[]) {
    float y = y0 + j * dy;
    int i = 0;

    for (; width - i >= 5; i += 5) {
        int pixel0 = i;
        int pixel1 = i + 1;
        int pixel2 = i + 2;
        int pixel3 = i + 3;
        int pixel4 = i + 4;

        float c_re0 = x0 + pixel0 * dx;
        float c_re1 = x0 + pixel1 * dx;
        float c_re2 = x0 + pixel2 * dx;
        float c_re3 = x0 + pixel3 * dx;
        float c_re4 = x0 + pixel4 * dx;

        int result[5];
        mandel_five(c_re0, y, c_re1, y, c_re2, y, c_re3, y, c_re4, y,
                    maxIterations, result);

        output[j * width + pixel0] = result[0];
        output[j * width + pixel1] = result[1];
        output[j * width + pixel2] = result[2];
        output[j * width + pixel3] = result[3];
        output[j * width + pixel4] = result[4];
    }

    for (; i < width; ++i) {
        float x = x0 + i * dx;
        output[j * width + i] = mandel(x, y, maxIterations);
    }
}

void mandelbrot_serial(float x0, float y0, float x1, float y1, int width,
                       int height, int maxIterations, int output[]) {
    float dx = (x1 - x0) / width;
    float dy = (y1 - y0) / height;

    for (int j = 0; j < height; ++j)
        mandelbrot_row(x0, y0, dx, dy, width, j, maxIterations, output);
}

extern "C" void run(const void* input1, const void* input2, void* output,
                    int n, int parameter, int threads) {
    const float* a = (const float*)input1;
    const int width = n * 3 / 2;
    const int height = n;
    int* pixels = (int*)output;

    if (threads <= 1) {
        mandelbrot_serial(a[0], a[1], a[2], a[3], width, height,
                          parameter, pixels);
        return;
    }

    const float dx = (a[2] - a[0]) / width;
    const float dy = (a[3] - a[1]) / height;

    #pragma omp parallel for schedule(dynamic, 1) num_threads(threads)
    for (int j = 0; j < height; ++j)
        mandelbrot_row(a[0], a[1], dx, dy, width, j, parameter, pixels);
}
