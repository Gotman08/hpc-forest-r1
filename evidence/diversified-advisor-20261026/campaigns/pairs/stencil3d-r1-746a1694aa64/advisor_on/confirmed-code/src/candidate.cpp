/*
  Copyright (c) 2010-2023, Intel Corporation

  SPDX-License-Identifier: BSD-3-Clause
*/

#include <cstddef>
#include <cstring>
#include <omp.h>

static void stencil_step(int x0, int x1, int y0, int y1, int z0, int z1, int Nx, int Ny, int Nz, const float coef[4],
                         const float *__restrict__ vsq, const float *__restrict__ Ain, float *__restrict__ Aout) {
    int Nxy = Nx * Ny;

    for (int z = z0; z < z1; ++z) {
        for (int y = y0; y < y1; ++y) {
#pragma omp simd
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
#undef A_cur
#undef A_next
}

static void stencil_step_parallel(int x0, int x1, int y0, int y1, int z0, int z1, int Nx, int Ny, int Nz,
                                  const float coef[4], const float *__restrict__ vsq,
                                  const float *__restrict__ Ain, float *__restrict__ Aout) {
    int Nxy = Nx * Ny;

    // All team members call this helper. The implicit worksharing barrier
    // completes each timestep before the buffers switch roles.
#pragma omp for schedule(static)
    for (int z = z0; z < z1; ++z) {
        for (int y = y0; y < y1; ++y) {
#pragma omp simd
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
#undef A_cur
#undef A_next
}

static void loop_stencil_serial(int t0, int t1, int x0, int x1, int y0, int y1, int z0, int z1, int Nx, int Ny,
                                int Nz, const float coef[4], const float vsq[], float Aeven[], float Aodd[]) {
    for (int t = t0; t < t1; ++t) {
        if ((t & 1) == 0)
            stencil_step(x0, x1, y0, y1, z0, z1, Nx, Ny, Nz, coef, vsq, Aeven, Aodd);
        else
            stencil_step(x0, x1, y0, y1, z0, z1, Nx, Ny, Nz, coef, vsq, Aodd, Aeven);
    }
}

static void loop_stencil_parallel(int t0, int t1, int x0, int x1, int y0, int y1, int z0, int z1, int Nx, int Ny,
                                  int Nz, const float coef[4], const float vsq[], float Aeven[], float Aodd[],
                                  int threads) {
#pragma omp parallel num_threads(threads)
    {
        for (int t = t0; t < t1; ++t) {
            if ((t & 1) == 0)
                stencil_step_parallel(x0, x1, y0, y1, z0, z1, Nx, Ny, Nz, coef, vsq, Aeven, Aodd);
            else
                stencil_step_parallel(x0, x1, y0, y1, z0, z1, Nx, Ny, Nz, coef, vsq, Aodd, Aeven);
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

    if (threads > 1)
        loop_stencil_parallel(0, 6, 4, n - 4, 4, n - 4, 4, n - 4, n, n, n, co, (const float*)input2, c, c + s,
                              threads);
    else
        loop_stencil_serial(0, 6, 4, n - 4, 4, n - 4, 4, n - 4, n, n, n, co, (const float*)input2, c, c + s);
}
