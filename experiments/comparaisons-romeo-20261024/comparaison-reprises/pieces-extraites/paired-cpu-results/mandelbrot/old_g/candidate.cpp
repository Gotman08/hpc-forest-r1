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

static void mandelbrot_serial(float x0, float y0, float x1, float y1, int width, int height, int maxIterations, int output[]) {
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

extern "C" void run(const void* input1, const void* input2, void* output, int n, int parameter, int threads) {
    const float* a = (const float*)input1;
    const int width = n * 3 / 2;
    const int height = n;
    int* result = (int*)output;

    if (threads <= 1) {
        mandelbrot_serial(a[0], a[1], a[2], a[3], width, height, parameter, result);
        return;
    }

    const float x0 = a[0];
    const float y0 = a[1];
    const float x1 = a[2];
    const float y1 = a[3];
    const float dx = (x1 - x0) / width;
    const float dy = (y1 - y0) / height;
    const int tile_width = 32;
    const int tile_height = 8;
    const int tile_columns = width / tile_width + (width % tile_width != 0);
    const int tile_rows = height / tile_height + (height % tile_height != 0);
    const int tile_count = tile_columns * tile_rows;

    #pragma omp parallel for schedule(dynamic, 1) num_threads(threads)
    for (int tile = 0; tile < tile_count; ++tile) {
        const int tile_column = tile % tile_columns;
        const int tile_row = tile / tile_columns;
        const int column_begin = tile_column * tile_width;
        const int row_begin = tile_row * tile_height;
        const int column_end = column_begin + std::min(tile_width, width - column_begin);
        const int row_end = row_begin + std::min(tile_height, height - row_begin);

        for (int j = row_begin; j < row_end; ++j) {
            for (int i = column_begin; i < column_end; ++i) {
                float x = x0 + i * dx;
                float y = y0 + j * dy;

                int index = (j * width + i);
                result[index] = mandel(x, y, parameter);
            }
        }
    }
}
