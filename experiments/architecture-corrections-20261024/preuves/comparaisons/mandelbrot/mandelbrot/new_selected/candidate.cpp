/*
  Copyright (c) 2010-2023, Intel Corporation

  SPDX-License-Identifier: BSD-3-Clause
*/

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

void mandelbrot_tiled(float x0, float y0, float x1, float y1,
                      int width, int height, int maxIterations,
                      int output[], int threads) {
    const float dx = (x1 - x0) / width;
    const float dy = (y1 - y0) / height;
    const int worker_count = threads > 1 ? threads : 1;
    const int tile_width = 32;
    const int tile_height = 8;
    const int tile_columns = width / tile_width + (width % tile_width != 0);
    const int tile_rows = height / tile_height + (height % tile_height != 0);

    #pragma omp parallel for collapse(2) schedule(dynamic, 1) num_threads(worker_count) if(threads > 1)
    for (int tile_y = 0; tile_y < tile_rows; ++tile_y) {
        for (int tile_x = 0; tile_x < tile_columns; ++tile_x) {
            const int j_begin = tile_y * tile_height;
            const int j_end = j_begin + std::min(tile_height, height - j_begin);
            const int i_begin = tile_x * tile_width;
            const int i_end = i_begin + std::min(tile_width, width - i_begin);

            for (int j = j_begin; j < j_end; ++j) {
                const float y = y0 + j * dy;
                const int row_offset = j * width;
                int i = i_begin;

                for (; i_end - i >= 8; i += 8) {
                    float c_re[8];
                    float z_re[8];
                    float z_im[8];
                    int active[8];

                    #pragma omp simd
                    for (int lane = 0; lane < 8; ++lane) {
                        const int pixel = i + lane;
                        const int index = row_offset + pixel;
                        c_re[lane] = x0 + pixel * dx;
                        z_re[lane] = c_re[lane];
                        z_im[lane] = y;
                        output[index] = maxIterations > 0 ? maxIterations : 0;
                        active[lane] = maxIterations > 0 ? 1 : 0;
                    }

                    int any_active = maxIterations > 0;
                    for (int iteration = 0;
                         iteration < maxIterations && any_active;
                         ++iteration) {
                        #pragma omp simd
                        for (int lane = 0; lane < 8; ++lane) {
                            if (active[lane]) {
                                if (z_re[lane] * z_re[lane] +
                                        z_im[lane] * z_im[lane] > 4.f) {
                                    output[row_offset + i + lane] = iteration;
                                    active[lane] = 0;
                                } else {
                                    float new_re = z_re[lane] * z_re[lane] -
                                                   z_im[lane] * z_im[lane];
                                    float new_im = 2.f * z_re[lane] * z_im[lane];
                                    z_re[lane] = c_re[lane] + new_re;
                                    z_im[lane] = y + new_im;
                                }
                            }
                        }

                        any_active = 0;
                        for (int lane = 0; lane < 8; ++lane)
                            any_active |= active[lane];
                    }
                }

                for (; i < i_end; ++i) {
                    const float x = x0 + i * dx;
                    output[row_offset + i] = mandel(x, y, maxIterations);
                }
            }
        }
    }
}

extern "C" void run(const void* input1, const void* input2, void* output,
                     int n, int parameter, int threads) {
    const float* bounds = static_cast<const float*>(input1);
    mandelbrot_tiled(bounds[0], bounds[1], bounds[2], bounds[3],
                     n * 3 / 2, n, parameter, static_cast<int*>(output), threads);
}
