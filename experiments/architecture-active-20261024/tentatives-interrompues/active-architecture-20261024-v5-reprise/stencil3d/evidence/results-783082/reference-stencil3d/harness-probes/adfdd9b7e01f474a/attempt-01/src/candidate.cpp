/*
  Copyright (c) 2010-2023, Intel Corporation

  SPDX-License-Identifier: BSD-3-Clause
*/

#include <cstdint>
#include <cstring>
#include <cmath>
#include <algorithm>
#include <omp.h>

static void stencil_step(int x0, int x1, int y0, int y1, int z0, int z1, int Nx, int Ny, int Nz, const float coef[4],
                         const float vsq[], const float Ain[], float Aout[]) {
    int Nxy = Nx * Ny;

    for (int z = z0; z < z1; ++z) {
        for (int y = y0; y < y1; ++y) {
            for (int x = x0; x < x1; ++x) {
                int index = (z * Nxy) + (y * Nx) + x;
#define A_cur(x, y, z) Ain[index + (x) + ((y)*Nx) + ((z)*Nxy)]
#define A_next(x, y, z) Aout[index + (x) + ((y)*Nx) + ((z)*Nxy)]
                float div = coef[0] * A_cur(0, 0, 0) +
                            coef[1] * (A_cur(+1, 0, 0) + A_cur(-1, 0, 0) + A_cur(0, +1, 0) + A_cur(0, -1, 0) +
                                       A_cur(0, 0, +1) + A_cur(0, 0, -1)) +
                            coef[2] * (A_cur(+2, 0, 0) + A_cur(-2, 0, 0) + A_cur(0, +2, 0) + A_cur(0, -2, 0) +
                                       A_cur(0, 0, +2) + A_cur(0, 0, -2)) +
                            coef[3] * (A_cur(+3, 0, 0) + A_cur(-3, 0, 0) + A_cur(0, +3, 0) + A_cur(0, -3, 0) +
                                       A_cur(0, 0, +3) + A_cur(0, 0, -3));

                A_next(0, 0, 0) = 2 * A_cur(0, 0, 0) - A_next(0, 0, 0) + vsq[index] * div;
            }
        }
    }
}

void loop_stencil_serial(int t0, int t1, int x0, int x1, int y0, int y1, int z0, int z1, int Nx, int Ny, int Nz,
                         const float coef[4], const float vsq[], float Aeven[], float Aodd[]) {
    for (int t = t0; t < t1; ++t) {
        if ((t & 1) == 0)
            stencil_step(x0, x1, y0, y1, z0, z1, Nx, Ny, Nz, coef, vsq, Aeven, Aodd);
        else
            stencil_step(x0, x1, y0, y1, z0, z1, Nx, Ny, Nz, coef, vsq, Aodd, Aeven);
    }
}

static inline void stencil_row(int y, int z, int x0, int x1, int Nx, int Nxy, const float coef[4], const float vsq[],
                               const float Ain[], float Aout[]) {
    int row_index = (z * Nxy) + (y * Nx);
    for (int x = x0; x < x1; ++x) {
        int index = row_index + x;
#define A_cur(x, y, z) Ain[index + (x) + ((y)*Nx) + ((z)*Nxy)]
#define A_next(x, y, z) Aout[index + (x) + ((y)*Nx) + ((z)*Nxy)]
        float div = coef[0] * A_cur(0, 0, 0) +
                    coef[1] * (A_cur(+1, 0, 0) + A_cur(-1, 0, 0) + A_cur(0, +1, 0) + A_cur(0, -1, 0) +
                               A_cur(0, 0, +1) + A_cur(0, 0, -1)) +
                    coef[2] * (A_cur(+2, 0, 0) + A_cur(-2, 0, 0) + A_cur(0, +2, 0) + A_cur(0, -2, 0) +
                               A_cur(0, 0, +2) + A_cur(0, 0, -2)) +
                    coef[3] * (A_cur(+3, 0, 0) + A_cur(-3, 0, 0) + A_cur(0, +3, 0) + A_cur(0, -3, 0) +
                               A_cur(0, 0, +3) + A_cur(0, 0, -3));

        A_next(0, 0, 0) = 2 * A_cur(0, 0, 0) - A_next(0, 0, 0) + vsq[index] * div;
#undef A_cur
#undef A_next
    }
}

static inline void stencil_row_tile(long long first_row, long long last_row, int y0, int y1, int z0, int Nx, int Nxy,
                                    const float coef[4], const float vsq[], const float Ain[], float Aout[]) {
    const int y_count = y1 - y0;
    int z = z0 + static_cast<int>(first_row / y_count);
    int y = y0 + static_cast<int>(first_row % y_count);

    for (long long row = first_row; row < last_row; ++row) {
        stencil_row(y, z, 0, Nx, Nx, Nxy, coef, vsq, Ain, Aout);
        if (++y == y1) {
            y = y0;
            ++z;
        }
    }
}

static void stencil_step_parallel_rows(int x0, int x1, int y0, int y1, int z0, int z1, int Nx, int Ny, int threads,
                                       const float coef[4], const float vsq[], const float Ain[], float Aout[]) {
    const int Nxy = Nx * Ny;
    const int y_count = y1 - y0;
    if (y_count <= 0 || z1 <= z0) return;
    const long long row_count = static_cast<long long>(z1 - z0) * static_cast<long long>(y_count);
    constexpr long long tile_rows = 16;
    const long long tile_count = (row_count + tile_rows - 1) / tile_rows;

#pragma omp parallel for schedule(static) num_threads(threads)
    for (long long tile = 0; tile < tile_count; ++tile) {
        const long long row_begin = tile * tile_rows;
        const long long remaining = row_count - row_begin;
        const long long row_end = row_begin + (remaining < tile_rows ? remaining : tile_rows);
        stencil_row_tile(row_begin, row_end, y0, y1, z0, Nx, Nxy, coef, vsq, Ain, Aout);
    }
}

static void loop_stencil_omp_per_timestep(int t0, int t1, int x0, int x1, int y0, int y1, int z0, int z1, int Nx,
                                          int Ny, int threads, const float coef[4], const float vsq[], float Aeven[],
                                          float Aodd[]) {
    for (int t = t0; t < t1; ++t) {
        if ((t & 1) == 0)
            stencil_step_parallel_rows(x0, x1, y0, y1, z0, z1, Nx, Ny, threads, coef, vsq, Aeven, Aodd);
        else
            stencil_step_parallel_rows(x0, x1, y0, y1, z0, z1, Nx, Ny, threads, coef, vsq, Aodd, Aeven);
    }
}

static void loop_stencil_omp_persistent(int t0, int t1, int x0, int x1, int y0, int y1, int z0, int z1, int Nx,
                                        int Ny, int threads, const float coef[4], const float vsq[], float Aeven[],
                                        float Aodd[]) {
    const int Nxy = Nx * Ny;
    const int y_count = y1 - y0;
    if (y_count <= 0 || z1 <= z0) return;
    const long long row_count = static_cast<long long>(z1 - z0) * static_cast<long long>(y_count);
    constexpr long long tile_rows = 16;
    const long long tile_count = (row_count + tile_rows - 1) / tile_rows;

#pragma omp parallel num_threads(threads)
    {
        for (int t = t0; t < t1; ++t) {
            const float* Ain;
            float* Aout;
            if ((t & 1) == 0) {
                Ain = Aeven;
                Aout = Aodd;
            } else {
                Ain = Aodd;
                Aout = Aeven;
            }

#pragma omp for schedule(static)
            for (long long tile = 0; tile < tile_count; ++tile) {
                const long long row_begin = tile * tile_rows;
                const long long remaining = row_count - row_begin;
                const long long row_end = row_begin + (remaining < tile_rows ? remaining : tile_rows);
                stencil_row_tile(row_begin, row_end, y0, y1, z0, Nx, Nxy, coef, vsq, Ain, Aout);
            }
        }
    }
}

extern "C" void run(const void* input1, const void* input2, void* output, int n, int parameter, int threads) {
    size_t s = size_t(n) * n * n;
    const float* a = (const float*)input1;
    float* c = (float*)output;
    memcpy(c, a, s * 4);
    memset(c + s, 0, s * 4);
    const float co[4] = {.5f, -.25f, .125f, -.0625f};

    const int x0 = 4;
    const int x1 = n - 4;
    const int y0 = 4;
    const int y1 = n - 4;
    const int z0 = 4;
    const int z1 = n - 4;
    size_t active_cells = 0;
    if (x1 > x0 && y1 > y0 && z1 > z0) {
        active_cells = size_t(x1 - x0) * size_t(y1 - y0) * size_t(z1 - z0);
    }

    if (threads <= 0 || active_cells <= 32768) {
        loop_stencil_serial(0, 6, x0, x1, y0, y1, z0, z1, n, n, n, co, (const float*)input2, c, c + s);
    } else if (threads == 1) {
        loop_stencil_omp_per_timestep(0, 6, x0, x1, y0, y1, z0, z1, n, n, threads, co, (const float*)input2, c,
                                      c + s);
    } else {
        loop_stencil_omp_persistent(0, 6, x0, x1, y0, y1, z0, z1, n, n, threads, co, (const float*)input2, c,
                                    c + s);
    }
}
