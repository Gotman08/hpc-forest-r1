/*
  Copyright (c) 2010-2023, Intel Corporation

  SPDX-License-Identifier: BSD-3-Clause
*/

#include <cstddef>
#include <cstdint>
#include <cstring>
#include <cmath>
#include <algorithm>
#include <omp.h>

static void stencil_step(int x0, int x1, int y0, int y1, int z0, int z1, int Nx, int Ny, int Nz,
                         const float *__restrict__ coef, const float *__restrict__ vsq,
                         const float *__restrict__ Ain, float *__restrict__ Aout) {
    int Nxy = Nx * Ny;

    // Each thread encounters this worksharing loop; its implicit barrier
    // completes a step before any thread starts the next one.
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
#undef A_cur
#undef A_next
        }
    }
}

static void loop_stencil_parallel(int t0, int t1, int x0, int x1, int y0, int y1, int z0, int z1, int Nx, int Ny, int Nz,
                                  const float coef[4], const float vsq[], float Aeven[], float Aodd[], int threads) {
    const int worker_count = threads > 0 ? threads : 1;

    #pragma omp parallel num_threads(worker_count)
    {
        for (int t = t0; t < t1; ++t) {
            const float *Ain;
            float *Aout;
            if ((t & 1) == 0) {
                Ain = Aeven;
                Aout = Aodd;
            } else {
                Ain = Aodd;
                Aout = Aeven;
            }
            stencil_step(x0, x1, y0, y1, z0, z1, Nx, Ny, Nz, coef, vsq, Ain, Aout);
        }
    }
}

extern "C" void run(const void *input1, const void *input2, void *output, int n, int parameter, int threads) {
    size_t s = size_t(n) * n * n;
    const float *a = static_cast<const float *>(input1);
    float *c = static_cast<float *>(output);
    memcpy(c, a, s * sizeof(float));
    memset(c + s, 0, s * sizeof(float));
    const float co[4] = {.5f, -.25f, .125f, -.0625f};
    loop_stencil_parallel(0, 6, 4, n - 4, 4, n - 4, 4, n - 4, n, n, n, co,
                          static_cast<const float *>(input2), c, c + s, threads);
}
