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
        int base = 0;

        for (; width - base >= 12; base += 12) {
            float c_re0 = x0 + (base + 0) * dx;
            float c_re1 = x0 + (base + 1) * dx;
            float c_re2 = x0 + (base + 2) * dx;
            float c_re3 = x0 + (base + 3) * dx;
            float c_re4 = x0 + (base + 4) * dx;
            float c_re5 = x0 + (base + 5) * dx;
            float c_re6 = x0 + (base + 6) * dx;
            float c_re7 = x0 + (base + 7) * dx;
            float c_re8 = x0 + (base + 8) * dx;
            float c_re9 = x0 + (base + 9) * dx;
            float c_re10 = x0 + (base + 10) * dx;
            float c_re11 = x0 + (base + 11) * dx;

            float z_re0 = c_re0, z_im0 = y;
            float z_re1 = c_re1, z_im1 = y;
            float z_re2 = c_re2, z_im2 = y;
            float z_re3 = c_re3, z_im3 = y;
            float z_re4 = c_re4, z_im4 = y;
            float z_re5 = c_re5, z_im5 = y;
            float z_re6 = c_re6, z_im6 = y;
            float z_re7 = c_re7, z_im7 = y;
            float z_re8 = c_re8, z_im8 = y;
            float z_re9 = c_re9, z_im9 = y;
            float z_re10 = c_re10, z_im10 = y;
            float z_re11 = c_re11, z_im11 = y;

            bool active0 = true, active1 = true, active2 = true, active3 = true;
            bool active4 = true, active5 = true, active6 = true, active7 = true;
            bool active8 = true, active9 = true, active10 = true, active11 = true;
            int count0 = 0, count1 = 0, count2 = 0, count3 = 0;
            int count4 = 0, count5 = 0, count6 = 0, count7 = 0;
            int count8 = 0, count9 = 0, count10 = 0, count11 = 0;

            for (int iter = 0; iter < maxIterations; ++iter) {
                bool any_active = false;

                if (active0) {
                    if (z_re0 * z_re0 + z_im0 * z_im0 > 4.f) active0 = false;
                    else {
                        float new_re0 = z_re0 * z_re0 - z_im0 * z_im0;
                        float new_im0 = 2.f * z_re0 * z_im0;
                        z_re0 = c_re0 + new_re0;
                        z_im0 = y + new_im0;
                        ++count0;
                        any_active = true;
                    }
                }
                if (active1) {
                    if (z_re1 * z_re1 + z_im1 * z_im1 > 4.f) active1 = false;
                    else {
                        float new_re1 = z_re1 * z_re1 - z_im1 * z_im1;
                        float new_im1 = 2.f * z_re1 * z_im1;
                        z_re1 = c_re1 + new_re1;
                        z_im1 = y + new_im1;
                        ++count1;
                        any_active = true;
                    }
                }
                if (active2) {
                    if (z_re2 * z_re2 + z_im2 * z_im2 > 4.f) active2 = false;
                    else {
                        float new_re2 = z_re2 * z_re2 - z_im2 * z_im2;
                        float new_im2 = 2.f * z_re2 * z_im2;
                        z_re2 = c_re2 + new_re2;
                        z_im2 = y + new_im2;
                        ++count2;
                        any_active = true;
                    }
                }
                if (active3) {
                    if (z_re3 * z_re3 + z_im3 * z_im3 > 4.f) active3 = false;
                    else {
                        float new_re3 = z_re3 * z_re3 - z_im3 * z_im3;
                        float new_im3 = 2.f * z_re3 * z_im3;
                        z_re3 = c_re3 + new_re3;
                        z_im3 = y + new_im3;
                        ++count3;
                        any_active = true;
                    }
                }
                if (active4) {
                    if (z_re4 * z_re4 + z_im4 * z_im4 > 4.f) active4 = false;
                    else {
                        float new_re4 = z_re4 * z_re4 - z_im4 * z_im4;
                        float new_im4 = 2.f * z_re4 * z_im4;
                        z_re4 = c_re4 + new_re4;
                        z_im4 = y + new_im4;
                        ++count4;
                        any_active = true;
                    }
                }
                if (active5) {
                    if (z_re5 * z_re5 + z_im5 * z_im5 > 4.f) active5 = false;
                    else {
                        float new_re5 = z_re5 * z_re5 - z_im5 * z_im5;
                        float new_im5 = 2.f * z_re5 * z_im5;
                        z_re5 = c_re5 + new_re5;
                        z_im5 = y + new_im5;
                        ++count5;
                        any_active = true;
                    }
                }
                if (active6) {
                    if (z_re6 * z_re6 + z_im6 * z_im6 > 4.f) active6 = false;
                    else {
                        float new_re6 = z_re6 * z_re6 - z_im6 * z_im6;
                        float new_im6 = 2.f * z_re6 * z_im6;
                        z_re6 = c_re6 + new_re6;
                        z_im6 = y + new_im6;
                        ++count6;
                        any_active = true;
                    }
                }
                if (active7) {
                    if (z_re7 * z_re7 + z_im7 * z_im7 > 4.f) active7 = false;
                    else {
                        float new_re7 = z_re7 * z_re7 - z_im7 * z_im7;
                        float new_im7 = 2.f * z_re7 * z_im7;
                        z_re7 = c_re7 + new_re7;
                        z_im7 = y + new_im7;
                        ++count7;
                        any_active = true;
                    }
                }
                if (active8) {
                    if (z_re8 * z_re8 + z_im8 * z_im8 > 4.f) active8 = false;
                    else {
                        float new_re8 = z_re8 * z_re8 - z_im8 * z_im8;
                        float new_im8 = 2.f * z_re8 * z_im8;
                        z_re8 = c_re8 + new_re8;
                        z_im8 = y + new_im8;
                        ++count8;
                        any_active = true;
                    }
                }
                if (active9) {
                    if (z_re9 * z_re9 + z_im9 * z_im9 > 4.f) active9 = false;
                    else {
                        float new_re9 = z_re9 * z_re9 - z_im9 * z_im9;
                        float new_im9 = 2.f * z_re9 * z_im9;
                        z_re9 = c_re9 + new_re9;
                        z_im9 = y + new_im9;
                        ++count9;
                        any_active = true;
                    }
                }
                if (active10) {
                    if (z_re10 * z_re10 + z_im10 * z_im10 > 4.f) active10 = false;
                    else {
                        float new_re10 = z_re10 * z_re10 - z_im10 * z_im10;
                        float new_im10 = 2.f * z_re10 * z_im10;
                        z_re10 = c_re10 + new_re10;
                        z_im10 = y + new_im10;
                        ++count10;
                        any_active = true;
                    }
                }
                if (active11) {
                    if (z_re11 * z_re11 + z_im11 * z_im11 > 4.f) active11 = false;
                    else {
                        float new_re11 = z_re11 * z_re11 - z_im11 * z_im11;
                        float new_im11 = 2.f * z_re11 * z_im11;
                        z_re11 = c_re11 + new_re11;
                        z_im11 = y + new_im11;
                        ++count11;
                        any_active = true;
                    }
                }

                if (!any_active)
                    break;
            }

            int row = j * width;
            output[row + base + 0] = count0;
            output[row + base + 1] = count1;
            output[row + base + 2] = count2;
            output[row + base + 3] = count3;
            output[row + base + 4] = count4;
            output[row + base + 5] = count5;
            output[row + base + 6] = count6;
            output[row + base + 7] = count7;
            output[row + base + 8] = count8;
            output[row + base + 9] = count9;
            output[row + base + 10] = count10;
            output[row + base + 11] = count11;
        }

        for (; base < width; ++base) {
            float x = x0 + base * dx;
            int index = (j * width + base);
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
