/*
  Copyright (c) 2010-2023, Intel Corporation

  SPDX-License-Identifier: BSD-3-Clause
*/

#include <cstdint>
#include <cstring>
#include <cmath>
#include <algorithm>
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

void mandelbrot_tiled(float x0, float y0, float x1, float y1, int width, int height, int maxIterations, int threads, int output[]) {
    float dx = (x1 - x0) / width;
    float dy = (y1 - y0) / height;

    const int tileWidth = 64;
    const int tileHeight = 16;
    const int tileColumns = width / tileWidth + (width % tileWidth != 0);
    const int tileRows = height / tileHeight + (height % tileHeight != 0);
    const int workers = threads > 1 ? threads : 1;

    #pragma omp parallel for collapse(2) schedule(dynamic, 4) num_threads(workers) if (workers > 1)
    for (int tileY = 0; tileY < tileRows; ++tileY) {
        for (int tileX = 0; tileX < tileColumns; ++tileX) {
            const int rowBegin = tileY * tileHeight;
            const int rowEnd = rowBegin + std::min(tileHeight, height - rowBegin);
            const int columnBegin = tileX * tileWidth;
            const int columnEnd = columnBegin + std::min(tileWidth, width - columnBegin);

            for (int j = rowBegin; j < rowEnd; ++j) {
                for (int i = columnBegin; i < columnEnd; ++i) {
                    float x = x0 + i * dx;
                    float y = y0 + j * dy;

                    int index = (j * width + i);
                    output[index] = mandel(x, y, maxIterations);
                }
            }
        }
    }
}

extern "C" void run(const void* input1, const void* input2, void* output, int n, int parameter, int threads)
{
    const float* a = (const float*)input1;
    mandelbrot_tiled(a[0], a[1], a[2], a[3], n * 3 / 2, n, parameter, threads, (int*)output);
}
