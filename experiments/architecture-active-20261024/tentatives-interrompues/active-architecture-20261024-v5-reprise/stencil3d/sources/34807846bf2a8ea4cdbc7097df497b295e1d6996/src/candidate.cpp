/*
  Copyright (c) 2010-2023, Intel Corporation

  SPDX-License-Identifier: BSD-3-Clause
*/

#include <algorithm>
#include <cstddef>
#include <cstring>

static inline void stencil_step(int x0, int x1, int y0, int y1, int z0, int z1, int Nx, int Ny, int Nz, const float coef[4],
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

static void stencil_step_blocked(int x0, int x1, int y0, int y1, int z0, int z1, int Nx, int Ny, int Nz,
                                const float coef[4], const float vsq[], const float Ain[], float Aout[]) {
    const int block_x = 64;
    const int block_y = 16;
    const int block_z = 8;

    for (int bz = z0; bz < z1; bz += block_z) {
        const int ez = std::min(z1, bz + block_z);
        for (int by = y0; by < y1; by += block_y) {
            const int ey = std::min(y1, by + block_y);
            for (int bx = x0; bx < x1; bx += block_x) {
                const int ex = std::min(x1, bx + block_x);
                stencil_step(bx, ex, by, ey, bz, ez, Nx, Ny, Nz, coef, vsq, Ain, Aout);
            }
        }
    }
}

void loop_stencil_serial(int t0, int t1, int x0, int x1, int y0, int y1, int z0, int z1, int Nx, int Ny, int Nz,
                         const float coef[4], const float vsq[], float Aeven[], float Aodd[]) {
    for (int t = t0; t < t1; ++t) {
        if ((t & 1) == 0)
            stencil_step_blocked(x0, x1, y0, y1, z0, z1, Nx, Ny, Nz, coef, vsq, Aeven, Aodd);
        else
            stencil_step_blocked(x0, x1, y0, y1, z0, z1, Nx, Ny, Nz, coef, vsq, Aodd, Aeven);
    }
}

extern "C" void run(const void* input1, const void* input2, void* output, int n, int parameter, int threads) {
    const std::size_t s = static_cast<std::size_t>(n) * n * n;
    const float* a = static_cast<const float*>(input1);
    float* c = static_cast<float*>(output);
    std::memcpy(c, a, s * sizeof(float));
    std::memset(c + s, 0, s * sizeof(float));
    const float co[4] = {0.5f, -0.25f, 0.125f, -0.0625f};
    loop_stencil_serial(0, 6, 4, n - 4, 4, n - 4, 4, n - 4, n, n, n, co, static_cast<const float*>(input2), c, c + s);
}
