/*
  Copyright (c) 2010-2023, Intel Corporation

  SPDX-License-Identifier: BSD-3-Clause
*/

#include <algorithm>
#include <cstddef>
#include <cstring>
#include <omp.h>

static inline void stencil_point(int x, int Nx, int Nxy, const float coef[4], const float* in_row,
                                 const float* vsq_row, float* out_row, const float* x_vals) {
    const float center = x_vals[0];
    const float div = coef[0] * center +
                      coef[1] * (x_vals[1] + x_vals[-1] + in_row[x + Nx] + in_row[x - Nx] +
                                 in_row[x + Nxy] + in_row[x - Nxy]) +
                      coef[2] * (x_vals[2] + x_vals[-2] + in_row[x + 2 * Nx] + in_row[x - 2 * Nx] +
                                 in_row[x + 2 * Nxy] + in_row[x - 2 * Nxy]) +
                      coef[3] * (x_vals[3] + x_vals[-3] + in_row[x + 3 * Nx] + in_row[x - 3 * Nx] +
                                 in_row[x + 3 * Nxy] + in_row[x - 3 * Nxy]);

    out_row[x] = 2 * center - out_row[x] + vsq_row[x] * div;
}

static void stencil_step(int x0, int x1, int y0, int y1, int z0, int z1, int Nx, int Ny, int Nz,
                         const float coef[4], const float vsq[], const float Ain[], float Aout[]) {
    const int Nxy = Nx * Ny;

    // The worksharing barrier completes this timestep before the next begins.
#pragma omp for collapse(2) schedule(static)
    for (int z = z0; z < z1; ++z) {
        for (int y = y0; y < y1; ++y) {
            const int row = z * Nxy + y * Nx;
            const float* const in_row = Ain + row;
            const float* const vsq_row = vsq + row;
            float* const out_row = Aout + row;
            const int span = x1 > x0 ? x1 - x0 : 0;
            const int block_count = span / 4;

#if defined(_OPENMP) && _OPENMP >= 201307
#pragma omp simd
#endif
            for (int block = 0; block < block_count; ++block) {
                const int x = x0 + 4 * block;
                float window[10];
                window[0] = in_row[x - 3];
                window[1] = in_row[x - 2];
                window[2] = in_row[x - 1];
                window[3] = in_row[x];
                window[4] = in_row[x + 1];
                window[5] = in_row[x + 2];
                window[6] = in_row[x + 3];
                window[7] = in_row[x + 4];
                window[8] = in_row[x + 5];
                window[9] = in_row[x + 6];

                stencil_point(x, Nx, Nxy, coef, in_row, vsq_row, out_row, window + 3);
                stencil_point(x + 1, Nx, Nxy, coef, in_row, vsq_row, out_row, window + 4);
                stencil_point(x + 2, Nx, Nxy, coef, in_row, vsq_row, out_row, window + 5);
                stencil_point(x + 3, Nx, Nxy, coef, in_row, vsq_row, out_row, window + 6);
            }

            int x = x0 + 4 * block_count;
            for (; x < x1; ++x) {
                const float center = in_row[x];
                const float div = coef[0] * center +
                                  coef[1] * (in_row[x + 1] + in_row[x - 1] + in_row[x + Nx] + in_row[x - Nx] +
                                             in_row[x + Nxy] + in_row[x - Nxy]) +
                                  coef[2] * (in_row[x + 2] + in_row[x - 2] + in_row[x + 2 * Nx] +
                                             in_row[x - 2 * Nx] + in_row[x + 2 * Nxy] + in_row[x - 2 * Nxy]) +
                                  coef[3] * (in_row[x + 3] + in_row[x - 3] + in_row[x + 3 * Nx] +
                                             in_row[x - 3 * Nx] + in_row[x + 3 * Nxy] + in_row[x - 3 * Nxy]);

                out_row[x] = 2 * center - out_row[x] + vsq_row[x] * div;
            }
        }
    }
}

static void loop_stencil_persistent(int t0, int t1, int x0, int x1, int y0, int y1, int z0, int z1, int Nx,
                                    int Ny, int Nz, const float coef[4], const float vsq[], float Aeven[],
                                    float Aodd[], int threads) {
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
