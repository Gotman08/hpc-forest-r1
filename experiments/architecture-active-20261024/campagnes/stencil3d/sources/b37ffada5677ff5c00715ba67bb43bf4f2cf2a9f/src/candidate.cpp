/*
  Copyright (c) 2010-2023, Intel Corporation

  SPDX-License-Identifier: BSD-3-Clause
*/

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

#include <cstddef>
#include <cstdint>
#include <cstring>
#include <cmath>
#include <algorithm>
#include <omp.h>

extern "C" void run(const void* input1, const void* input2, void* output, int n, int parameter, int threads) {
    const std::size_t s = static_cast<std::size_t>(n) * n * n;
    const float* a = static_cast<const float*>(input1);
    const float* vsq = static_cast<const float*>(input2);
    float* c = static_cast<float*>(output);

    std::memcpy(c, a, s * sizeof(float));
    std::memset(c + s, 0, s * sizeof(float));

    const float co[4] = {0.5f, -0.25f, 0.125f, -0.0625f};
    const int tile = 64;
    const int lo = 4;
    const int hi = n - 4;

    // Spatial-only tiled control: retain a global timestep barrier and use the
    // same static 3-D tile schedule for every step, without a temporal halo.
#pragma omp parallel num_threads(threads)
    {
        for (int t = 0; t < 6; ++t) {
            const float* src = ((t & 1) == 0) ? c : c + s;
            float* dst = ((t & 1) == 0) ? c + s : c;

#pragma omp for collapse(3) schedule(static)
            for (int z0 = lo; z0 < hi; z0 += tile) {
                for (int y0 = lo; y0 < hi; y0 += tile) {
                    for (int x0 = lo; x0 < hi; x0 += tile) {
                        const int z1 = (z0 + tile < hi) ? z0 + tile : hi;
                        const int y1 = (y0 + tile < hi) ? y0 + tile : hi;
                        const int x1 = (x0 + tile < hi) ? x0 + tile : hi;
                        stencil_step(x0, x1, y0, y1, z0, z1, n, n, n, co, vsq, src, dst);
                    }
                }
            }
        }
    }
}
