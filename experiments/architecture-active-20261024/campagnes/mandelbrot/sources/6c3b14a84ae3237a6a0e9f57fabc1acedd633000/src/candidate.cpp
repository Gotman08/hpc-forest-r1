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
        float y = y0 + j * dy;
        int i = 0;

        for (; i <= width - 6; i += 6) {
            float c_re0 = x0 + i * dx;
            float c_re1 = x0 + (i + 1) * dx;
            float c_re2 = x0 + (i + 2) * dx;
            float c_re3 = x0 + (i + 3) * dx;
            float c_re4 = x0 + (i + 4) * dx;
            float c_re5 = x0 + (i + 5) * dx;

            float z_re0 = c_re0, z_im0 = y;
            float z_re1 = c_re1, z_im1 = y;
            float z_re2 = c_re2, z_im2 = y;
            float z_re3 = c_re3, z_im3 = y;
            float z_re4 = c_re4, z_im4 = y;
            float z_re5 = c_re5, z_im5 = y;

            bool active0 = true, active1 = true, active2 = true;
            bool active3 = true, active4 = true, active5 = true;
            int count0 = 0, count1 = 0, count2 = 0;
            int count3 = 0, count4 = 0, count5 = 0;

            for (int iteration = 0;
                 iteration < maxIterations &&
                     (active0 || active1 || active2 || active3 || active4 || active5);
                 ++iteration) {
                if (active0) {
                    if (z_re0 * z_re0 + z_im0 * z_im0 > 4.f) {
                        active0 = false;
                    } else {
                        float new_re = z_re0 * z_re0 - z_im0 * z_im0;
                        float new_im = 2.f * z_re0 * z_im0;
                        z_re0 = c_re0 + new_re;
                        z_im0 = y + new_im;
                        ++count0;
                    }
                }
                if (active1) {
                    if (z_re1 * z_re1 + z_im1 * z_im1 > 4.f) {
                        active1 = false;
                    } else {
                        float new_re = z_re1 * z_re1 - z_im1 * z_im1;
                        float new_im = 2.f * z_re1 * z_im1;
                        z_re1 = c_re1 + new_re;
                        z_im1 = y + new_im;
                        ++count1;
                    }
                }
                if (active2) {
                    if (z_re2 * z_re2 + z_im2 * z_im2 > 4.f) {
                        active2 = false;
                    } else {
                        float new_re = z_re2 * z_re2 - z_im2 * z_im2;
                        float new_im = 2.f * z_re2 * z_im2;
                        z_re2 = c_re2 + new_re;
                        z_im2 = y + new_im;
                        ++count2;
                    }
                }
                if (active3) {
                    if (z_re3 * z_re3 + z_im3 * z_im3 > 4.f) {
                        active3 = false;
                    } else {
                        float new_re = z_re3 * z_re3 - z_im3 * z_im3;
                        float new_im = 2.f * z_re3 * z_im3;
                        z_re3 = c_re3 + new_re;
                        z_im3 = y + new_im;
                        ++count3;
                    }
                }
                if (active4) {
                    if (z_re4 * z_re4 + z_im4 * z_im4 > 4.f) {
                        active4 = false;
                    } else {
                        float new_re = z_re4 * z_re4 - z_im4 * z_im4;
                        float new_im = 2.f * z_re4 * z_im4;
                        z_re4 = c_re4 + new_re;
                        z_im4 = y + new_im;
                        ++count4;
                    }
                }
                if (active5) {
                    if (z_re5 * z_re5 + z_im5 * z_im5 > 4.f) {
                        active5 = false;
                    } else {
                        float new_re = z_re5 * z_re5 - z_im5 * z_im5;
                        float new_im = 2.f * z_re5 * z_im5;
                        z_re5 = c_re5 + new_re;
                        z_im5 = y + new_im;
                        ++count5;
                    }
                }
            }

            int base_index = j * width + i;
            output[base_index] = count0;
            output[base_index + 1] = count1;
            output[base_index + 2] = count2;
            output[base_index + 3] = count3;
            output[base_index + 4] = count4;
            output[base_index + 5] = count5;
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
