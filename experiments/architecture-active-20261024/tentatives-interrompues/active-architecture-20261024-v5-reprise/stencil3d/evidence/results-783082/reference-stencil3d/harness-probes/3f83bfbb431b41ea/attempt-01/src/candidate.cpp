/*
  Copyright (c) 2010-2023, Intel Corporation

  SPDX-License-Identifier: BSD-3-Clause
*/

static void stencil_row(int y, int z, int x0, int x1, int Nx, int Nxy, const float coef[4],
                        const float vsq[], const float Ain[], float Aout[]) {
    int row_base = z * Nxy + y * Nx;
    for (int x = x0; x < x1; ++x) {
        int index = row_base + x;
#define A_cur(x, y, z) Ain[index + (x) + ((y) * Nx) + ((z) * Nxy)]
#define A_next(x, y, z) Aout[index + (x) + ((y) * Nx) + ((z) * Nxy)]
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

static void stencil_step(int x0, int x1, int y0, int y1, int z0, int z1, int Nx, int Ny, int Nz,
                         const float coef[4], const float vsq[], const float Ain[], float Aout[]) {
    int Nxy = Nx * Ny;
    for (int z = z0; z < z1; ++z) {
        for (int y = y0; y < y1; ++y) {
            stencil_row(y, z, x0, x1, Nx, Nxy, coef, vsq, Ain, Aout);
        }
    }
}

static void stencil_row_block(long long block, long long total_rows, int rows_per_block, int rows_per_plane,
                              int x0, int x1, int y0, int y1, int z0, int Nx, int Nxy,
                              const float coef[4], const float vsq[], const float Ain[], float Aout[]) {
    long long row = block * rows_per_block;
    long long row_end = row + rows_per_block;
    if (row_end > total_rows)
        row_end = total_rows;

    int z = z0 + static_cast<int>(row / rows_per_plane);
    int y = y0 + static_cast<int>(row % rows_per_plane);
    for (; row < row_end; ++row) {
        stencil_row(y, z, x0, x1, Nx, Nxy, coef, vsq, Ain, Aout);
        ++y;
        if (y == y1) {
            y = y0;
            ++z;
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

#include <cstdint>
#include <cstring>
#include <cmath>
#include <algorithm>
#include <omp.h>

extern "C" void run(const void* input1, const void* input2, void* output, int n, int parameter, int threads) {
    size_t s = size_t(n) * n * n;
    const float* a = static_cast<const float*>(input1);
    float* c = static_cast<float*>(output);
    memcpy(c, a, s * 4);
    memset(c + s, 0, s * 4);

    const float co[4] = {.5f, -.25f, .125f, -.0625f};
    const float* vsq = static_cast<const float*>(input2);
    const int x0 = 4;
    const int x1 = n - 4;
    const int y0 = 4;
    const int y1 = n - 4;
    const int z0 = 4;
    const int z1 = n - 4;
    const int active_x = x1 - x0;
    const int active_y = y1 - y0;
    const int active_z = z1 - z0;

    if (threads <= 0 || active_x <= 0 || active_y <= 0 || active_z <= 0) {
        loop_stencil_serial(0, 6, x0, x1, y0, y1, z0, z1, n, n, n, co, vsq, c, c + s);
        return;
    }

    const long long work_items = 6LL * active_x * active_y * active_z;
    if (work_items < 262144LL) {
        loop_stencil_serial(0, 6, x0, x1, y0, y1, z0, z1, n, n, n, co, vsq, c, c + s);
        return;
    }

    const int rows_per_block = 8;
    const int rows_per_plane = active_y;
    const long long total_rows = static_cast<long long>(active_y) * active_z;
    const long long block_count = (total_rows + rows_per_block - 1) / rows_per_block;
    int team_size = threads;
    if (block_count < team_size)
        team_size = static_cast<int>(block_count);
    const int Nxy = n * n;
    float* Aeven = c;
    float* Aodd = c + s;

    if (threads == 1) {
        for (int t = 0; t < 6; ++t) {
            const float* Ain = (t & 1) ? Aodd : Aeven;
            float* Aout = (t & 1) ? Aeven : Aodd;
#pragma omp parallel for schedule(static) num_threads(team_size)
            for (long long block = 0; block < block_count; ++block) {
                stencil_row_block(block, total_rows, rows_per_block, rows_per_plane, x0, x1, y0, y1, z0,
                                  n, Nxy, co, vsq, Ain, Aout);
            }
        }
    } else {
#pragma omp parallel num_threads(team_size)
        {
            for (int t = 0; t < 6; ++t) {
                const float* Ain = (t & 1) ? Aodd : Aeven;
                float* Aout = (t & 1) ? Aeven : Aodd;
#pragma omp for schedule(static)
                for (long long block = 0; block < block_count; ++block) {
                    stencil_row_block(block, total_rows, rows_per_block, rows_per_plane, x0, x1, y0, y1, z0,
                                      n, Nxy, co, vsq, Ain, Aout);
                }
            }
        }
    }
}
