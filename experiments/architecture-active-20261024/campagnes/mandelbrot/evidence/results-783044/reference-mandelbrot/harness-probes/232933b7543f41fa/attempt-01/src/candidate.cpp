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

static inline void mandel8(float c_re0, float c_re1, float c_re2, float c_re3,
                           float c_re4, float c_re5, float c_re6, float c_re7,
                           float c_im, int count, int output[8]) {
    float z_re0 = c_re0, z_im0 = c_im;
    float z_re1 = c_re1, z_im1 = c_im;
    float z_re2 = c_re2, z_im2 = c_im;
    float z_re3 = c_re3, z_im3 = c_im;
    float z_re4 = c_re4, z_im4 = c_im;
    float z_re5 = c_re5, z_im5 = c_im;
    float z_re6 = c_re6, z_im6 = c_im;
    float z_re7 = c_re7, z_im7 = c_im;

    int result0 = count > 0 ? count : 0;
    int result1 = count > 0 ? count : 0;
    int result2 = count > 0 ? count : 0;
    int result3 = count > 0 ? count : 0;
    int result4 = count > 0 ? count : 0;
    int result5 = count > 0 ? count : 0;
    int result6 = count > 0 ? count : 0;
    int result7 = count > 0 ? count : 0;

    bool active0 = count > 0;
    bool active1 = count > 0;
    bool active2 = count > 0;
    bool active3 = count > 0;
    bool active4 = count > 0;
    bool active5 = count > 0;
    bool active6 = count > 0;
    bool active7 = count > 0;

    for (int iteration = 0;
         iteration < count && (active0 || active1 || active2 || active3 ||
                               active4 || active5 || active6 || active7);
         ++iteration) {
        if (active0) {
            if (z_re0 * z_re0 + z_im0 * z_im0 > 4.f) {
                result0 = iteration;
                active0 = false;
            } else {
                float new_re0 = z_re0 * z_re0 - z_im0 * z_im0;
                float new_im0 = 2.f * z_re0 * z_im0;
                z_re0 = c_re0 + new_re0;
                z_im0 = c_im + new_im0;
            }
        }
        if (active1) {
            if (z_re1 * z_re1 + z_im1 * z_im1 > 4.f) {
                result1 = iteration;
                active1 = false;
            } else {
                float new_re1 = z_re1 * z_re1 - z_im1 * z_im1;
                float new_im1 = 2.f * z_re1 * z_im1;
                z_re1 = c_re1 + new_re1;
                z_im1 = c_im + new_im1;
            }
        }
        if (active2) {
            if (z_re2 * z_re2 + z_im2 * z_im2 > 4.f) {
                result2 = iteration;
                active2 = false;
            } else {
                float new_re2 = z_re2 * z_re2 - z_im2 * z_im2;
                float new_im2 = 2.f * z_re2 * z_im2;
                z_re2 = c_re2 + new_re2;
                z_im2 = c_im + new_im2;
            }
        }
        if (active3) {
            if (z_re3 * z_re3 + z_im3 * z_im3 > 4.f) {
                result3 = iteration;
                active3 = false;
            } else {
                float new_re3 = z_re3 * z_re3 - z_im3 * z_im3;
                float new_im3 = 2.f * z_re3 * z_im3;
                z_re3 = c_re3 + new_re3;
                z_im3 = c_im + new_im3;
            }
        }
        if (active4) {
            if (z_re4 * z_re4 + z_im4 * z_im4 > 4.f) {
                result4 = iteration;
                active4 = false;
            } else {
                float new_re4 = z_re4 * z_re4 - z_im4 * z_im4;
                float new_im4 = 2.f * z_re4 * z_im4;
                z_re4 = c_re4 + new_re4;
                z_im4 = c_im + new_im4;
            }
        }
        if (active5) {
            if (z_re5 * z_re5 + z_im5 * z_im5 > 4.f) {
                result5 = iteration;
                active5 = false;
            } else {
                float new_re5 = z_re5 * z_re5 - z_im5 * z_im5;
                float new_im5 = 2.f * z_re5 * z_im5;
                z_re5 = c_re5 + new_re5;
                z_im5 = c_im + new_im5;
            }
        }
        if (active6) {
            if (z_re6 * z_re6 + z_im6 * z_im6 > 4.f) {
                result6 = iteration;
                active6 = false;
            } else {
                float new_re6 = z_re6 * z_re6 - z_im6 * z_im6;
                float new_im6 = 2.f * z_re6 * z_im6;
                z_re6 = c_re6 + new_re6;
                z_im6 = c_im + new_im6;
            }
        }
        if (active7) {
            if (z_re7 * z_re7 + z_im7 * z_im7 > 4.f) {
                result7 = iteration;
                active7 = false;
            } else {
                float new_re7 = z_re7 * z_re7 - z_im7 * z_im7;
                float new_im7 = 2.f * z_re7 * z_im7;
                z_re7 = c_re7 + new_re7;
                z_im7 = c_im + new_im7;
            }
        }
    }

    output[0] = result0;
    output[1] = result1;
    output[2] = result2;
    output[3] = result3;
    output[4] = result4;
    output[5] = result5;
    output[6] = result6;
    output[7] = result7;
}

static inline void mandelbrot_row(float x0, float y0, float dx, float dy,
                                  int width, int maxIterations, int output[],
                                  int j) {
    int i = 0;
    for (; width - i >= 8; i += 8) {
        int index = j * width + i;
        float c_re0 = x0 + i * dx;
        float c_re1 = x0 + (i + 1) * dx;
        float c_re2 = x0 + (i + 2) * dx;
        float c_re3 = x0 + (i + 3) * dx;
        float c_re4 = x0 + (i + 4) * dx;
        float c_re5 = x0 + (i + 5) * dx;
        float c_re6 = x0 + (i + 6) * dx;
        float c_re7 = x0 + (i + 7) * dx;
        float c_im = y0 + j * dy;
        mandel8(c_re0, c_re1, c_re2, c_re3, c_re4, c_re5, c_re6,
                c_re7, c_im, maxIterations, output + index);
    }

    for (; i < width; ++i) {
        float x = x0 + i * dx;
        float y = y0 + j * dy;
        int index = j * width + i;
        output[index] = mandel(x, y, maxIterations);
    }
}

static void mandelbrot_compute(float x0, float y0, float x1, float y1,
                               int width, int height, int maxIterations,
                               int output[], int threads) {
    float dx = (x1 - x0) / width;
    float dy = (y1 - y0) / height;
    int team_size = threads < height ? threads : height;

    if (team_size <= 1) {
        for (int j = 0; j < height; ++j)
            mandelbrot_row(x0, y0, dx, dy, width, maxIterations, output, j);
        return;
    }

#pragma omp parallel for schedule(guided, 4) num_threads(team_size)
    for (int j = 0; j < height; ++j)
        mandelbrot_row(x0, y0, dx, dy, width, maxIterations, output, j);
}

#include <cstdint>
#include <cstring>
#include <cmath>
#include <algorithm>
#include <omp.h>
extern "C" void run(const void* input1,const void* input2,void* output,int n,int parameter,int threads)
{const float*a=(const float*)input1;mandelbrot_compute(a[0],a[1],a[2],a[3],n*3/2,n,parameter,(int*)output,threads);}
