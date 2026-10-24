/*
  Copyright (c) 2010-2023, Intel Corporation

  SPDX-License-Identifier: BSD-3-Clause
*/

#include <cstdint>
#include <cstring>
#include <cmath>
#include <algorithm>
#include <omp.h>

#define STENCIL_UPDATE(X) \
    { \
        const float center = in_line[(X)]; \
        const float div = coef[0] * center + \
                          coef[1] * (in_line[(X) + 1] + in_line[(X) - 1] + in_line[(X) + Nx] + in_line[(X) - Nx] + \
                                     in_line[(X) + Nxy] + in_line[(X) - Nxy]) + \
                          coef[2] * (in_line[(X) + 2] + in_line[(X) - 2] + in_line[(X) + 2 * Nx] + in_line[(X) - 2 * Nx] + \
                                     in_line[(X) + 2 * Nxy] + in_line[(X) - 2 * Nxy]) + \
                          coef[3] * (in_line[(X) + 3] + in_line[(X) - 3] + in_line[(X) + 3 * Nx] + in_line[(X) - 3 * Nx] + \
                                     in_line[(X) + 3 * Nxy] + in_line[(X) - 3 * Nxy]); \
        out_line[(X)] = 2 * center - out_line[(X)] + vsq_line[(X)] * div; \
    }

static void stencil_step(int x0, int x1, int y0, int y1, int z0, int z1, int Nx, int Ny, int Nz, const float coef[4],
                         const float vsq[], const float Ain[], float Aout[]) {
    int Nxy = Nx * Ny;
    const int row_length = x1 - x0;

    for (int z = z0; z < z1; ++z) {
        for (int y = y0; y < y1; ++y) {
            int row_start = z * Nxy + y * Nx + x0;
            const float* in_line = Ain + row_start;
            const float* vsq_line = vsq + row_start;
            float* out_line = Aout + row_start;

#if defined(_OPENMP) && _OPENMP >= 201307
            const bool line_aligned =
                (reinterpret_cast<std::uintptr_t>(in_line) & 15u) == 0u &&
                (reinterpret_cast<std::uintptr_t>(vsq_line) & 15u) == 0u &&
                (reinterpret_cast<std::uintptr_t>(out_line) & 15u) == 0u;

            if (line_aligned) {
#pragma omp simd aligned(in_line, vsq_line, out_line : 16)
                for (int x = 0; x < row_length; ++x) {
                    STENCIL_UPDATE(x);
                }
            } else {
#pragma omp simd
                for (int x = 0; x < row_length; ++x) {
                    STENCIL_UPDATE(x);
                }
            }
#else
            for (int x = 0; x < row_length; ++x) {
                STENCIL_UPDATE(x);
            }
#endif
        }
    }
}

#undef STENCIL_UPDATE

void loop_stencil_serial(int t0, int t1, int x0, int x1, int y0, int y1, int z0, int z1, int Nx, int Ny, int Nz,
                         const float coef[4], const float vsq[], float Aeven[], float Aodd[]) {
    for (int t = t0; t < t1; ++t) {
        if ((t & 1) == 0)
            stencil_step(x0, x1, y0, y1, z0, z1, Nx, Ny, Nz, coef, vsq, Aeven, Aodd);
        else
            stencil_step(x0, x1, y0, y1, z0, z1, Nx, Ny, Nz, coef, vsq, Aodd, Aeven);
    }
}

extern "C" void run(const void* input1, const void* input2, void* output, int n, int parameter, int threads) {
    size_t s = size_t(n) * n * n;
    const float* a = (const float*)input1;
    float* c = (float*)output;
    memcpy(c, a, s * 4);
    memset(c + s, 0, s * 4);
    const float co[4] = {.5f, -.25f, .125f, -.0625f};
    loop_stencil_serial(0, 6, 4, n - 4, 4, n - 4, 4, n - 4, n, n, n, co, (const float*)input2, c, c + s);
}
