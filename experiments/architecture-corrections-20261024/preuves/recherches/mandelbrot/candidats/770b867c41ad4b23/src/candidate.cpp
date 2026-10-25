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

#include <cstdint>
#include <cstring>
#include <cmath>
#include <algorithm>
#include <omp.h>

void mandelbrot_serial(float x0, float y0, float x1, float y1, int width, int height, int maxIterations, int output[], int threads) {
    float dx = (x1 - x0) / width;
    float dy = (y1 - y0) / height;
    const int tileWidth = 32;
    const int tileHeight = 8;
    const int tileColumns = width / tileWidth + (width % tileWidth > 0 ? 1 : 0);
    const int tileRows = height / tileHeight + (height % tileHeight > 0 ? 1 : 0);
    const int workers = std::max(threads, 1);

    #pragma omp parallel for collapse(2) schedule(dynamic, 1) num_threads(workers) if(workers > 1)
    for (int tileY = 0; tileY < tileRows; ++tileY) {
        for (int tileX = 0; tileX < tileColumns; ++tileX) {
            const int jBegin = tileY * tileHeight;
            const int iBegin = tileX * tileWidth;
            const int jEnd = jBegin + std::min(tileHeight, height - jBegin);
            const int iEnd = iBegin + std::min(tileWidth, width - iBegin);

            for (int j = jBegin; j < jEnd; ++j) {
                for (int i = iBegin; i < iEnd; ++i) {
                    float x = x0 + i * dx;
                    float y = y0 + j * dy;

                    int index = (j * width + i);
                    output[index] = mandel(x, y, maxIterations);
                }
            }
        }
    }
}

extern "C" void run(const void* input1,const void* input2,void* output,int n,int parameter,int threads)
{
    const float* a = (const float*)input1;
    mandelbrot_serial(a[0], a[1], a[2], a[3], n * 3 / 2, n, parameter, (int*)output, threads);
}
