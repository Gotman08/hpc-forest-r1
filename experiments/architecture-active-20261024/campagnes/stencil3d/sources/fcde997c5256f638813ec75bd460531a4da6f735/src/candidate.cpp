/*
  Copyright (c) 2010-2023, Intel Corporation

  SPDX-License-Identifier: BSD-3-Clause
*/

#include <algorithm>
#include <cstddef>
#include <cstring>
#include <omp.h>

static void stencil_step(int x0, int x1, int y0, int y1, int z0, int z1, int Nx, int Ny, int Nz, const float coef[4],
                         const float vsq[], const float Ain[], float Aout[]) {
    const int Nxy = Nx * Ny;

    // The worksharing barrier completes this timestep before the next begins.
#pragma omp for collapse(2) schedule(static)
    for (int z = z0; z < z1; ++z) {
        for (int y = y0; y < y1; ++y) {
            const int row = z * Nxy + y * Nx;
            const float* const in_row = Ain + row;
            const float* const vsq_row = vsq + row;
            float* const out_row = Aout + row;

            // Keep a rolling radius-3 window for the contiguous x neighbors.
            // The guard avoids reading the window when the x range is empty.
            if (x0 < x1) {
                float xm3 = in_row[x0 - 3];
                float xm2 = in_row[x0 - 2];
                float xm1 = in_row[x0 - 1];
                float xcenter = in_row[x0];
                float xp1 = in_row[x0 + 1];
                float xp2 = in_row[x0 + 2];
                float xp3 = in_row[x0 + 3];

                for (int x = x0; x < x1; ++x) {
                    const float center = xcenter;
                    const float div = coef[0] * center +
                                      coef[1] * (xp1 + xm1 + in_row[x + Nx] + in_row[x - Nx] +
                                                 in_row[x + Nxy] + in_row[x - Nxy]) +
                                      coef[2] * (xp2 + xm2 + in_row[x + 2 * Nx] + in_row[x - 2 * Nx] +
                                                 in_row[x + 2 * Nxy] + in_row[x - 2 * Nxy]) +
                                      coef[3] * (xp3 + xm3 + in_row[x + 3 * Nx] + in_row[x - 3 * Nx] +
                                                 in_row[x + 3 * Nxy] + in_row[x - 3 * Nxy]);

                    out_row[x] = 2 * center - out_row[x] + vsq_row[x] * div;

                    xm3 = xm2;
                    xm2 = xm1;
                    xm1 = xcenter;
                    xcenter = xp1;
                    xp1 = xp2;
                    xp2 = xp3;
                    xp3 = in_row[x + 4];
                }
            }
        }
    }
}

static void loop_stencil_persistent(int t0, int t1, int x0, int x1, int y0, int y1, int z0, int z1, int Nx, int Ny,
                                    int Nz, const float coef[4], const float vsq[], float Aeven[], float Aodd[],
                                    int threads) {
    const int team_size = std::max(1, threads);
#pragma omp parallel num_threads(team_size)
    {
        for (int t = t0; t < t1; ++t) {
            if ((t & 1) == 0)
                stencil_step(x0, x1, y0, y1, z0, z1, Nx, Ny, Nz, coef, vsq, Aeven, Aodd);
            else
                stencil_step(x0, x1, y0, y1, z0, z1, Nx, Ny, Nz, coef, vsq, Aodd, Aeven);
        }
    }
}

extern "C" void run(const void* input1, const void* input2, void* output, int n, int parameter, int threads) {
    const std::size_t s = std::size_t(n) * n * n;
    const float* const a = static_cast<const float*>(input1);
    float* const c = static_cast<float*>(output);
    std::memcpy(c, a, s * sizeof(float));
    std::memset(c + s, 0, s * sizeof(float));

    const float co[4] = {0.5f, -0.25f, 0.125f, -0.0625f};
    loop_stencil_persistent(0, 6, 4, n - 4, 4, n - 4, 4, n - 4, n, n, n, co, static_cast<const float*>(input2), c,
                            c + s, threads);
}
