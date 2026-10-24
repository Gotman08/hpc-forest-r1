/*
  Copyright (c) 2010-2023, Intel Corporation

  SPDX-License-Identifier: BSD-3-Clause
*/

#include <cstddef>
#include <cstring>
#include <omp.h>

static void stencil_step(int x0, int x1, int y0, int y1, int z0, int z1, int Nx, int Ny, int Nz, const float coef[4],
                         const float vsq[], const float Ain[], float Aout[]) {
    const int Nxy = Nx * Ny;
    const float c0 = coef[0];
    const float c1 = coef[1];
    const float c2 = coef[2];
    const float c3 = coef[3];

#pragma omp for collapse(2) schedule(static)
    for (int z = z0; z < z1; ++z) {
        for (int y = y0; y < y1; ++y) {
            const int row = z * Nxy + y * Nx;
#pragma omp simd
            for (int x = x0; x < x1; ++x) {
                const int index = row + x;
                const float* p = Ain + index;
                const float div = c0 * p[0] +
                                  c1 * (p[1] + p[-1] + p[Nx] + p[-Nx] + p[Nxy] + p[-Nxy]) +
                                  c2 * (p[2] + p[-2] + p[2 * Nx] + p[-2 * Nx] + p[2 * Nxy] + p[-2 * Nxy]) +
                                  c3 * (p[3] + p[-3] + p[3 * Nx] + p[-3 * Nx] + p[3 * Nxy] + p[-3 * Nxy]);

                Aout[index] = 2.0f * p[0] - Aout[index] + vsq[index] * div;
            }
        }
    }
}

static void loop_stencil_parallel(int t0, int t1, int x0, int x1, int y0, int y1, int z0, int z1, int Nx, int Ny, int Nz,
                                  const float coef[4], const float vsq[], float Aeven[], float Aodd[], int threads) {
    const int team_size = threads > 0 ? threads : 1;

#pragma omp parallel num_threads(team_size)
    {
        for (int t = t0; t < t1; ++t) {
            if ((t & 1) == 0) {
                stencil_step(x0, x1, y0, y1, z0, z1, Nx, Ny, Nz, coef, vsq, Aeven, Aodd);
            } else {
                stencil_step(x0, x1, y0, y1, z0, z1, Nx, Ny, Nz, coef, vsq, Aodd, Aeven);
            }
        }
    }
}

extern "C" void run(const void* input1, const void* input2, void* output, int n, int parameter, int threads) {
    const std::size_t s = static_cast<std::size_t>(n) * n * n;
    const float* a = static_cast<const float*>(input1);
    float* c = static_cast<float*>(output);

    std::memcpy(c, a, s * sizeof(float));
    std::memset(c + s, 0, s * sizeof(float));

    const float coef[4] = {0.5f, -0.25f, 0.125f, -0.0625f};
    loop_stencil_parallel(0, 6, 4, n - 4, 4, n - 4, 4, n - 4, n, n, n, coef,
                          static_cast<const float*>(input2), c, c + s, threads);
}
