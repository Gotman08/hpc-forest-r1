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

#define STENCIL_UPDATE(IN, V, OUT, I) \
    do { \
        const int stencil_index = (I); \
        float div = coef[0] * (IN)[stencil_index] + \
                    coef[1] * ((IN)[stencil_index + 1] + (IN)[stencil_index - 1] + \
                               (IN)[stencil_index + Nx] + (IN)[stencil_index - Nx] + \
                               (IN)[stencil_index + Nxy] + (IN)[stencil_index - Nxy]) + \
                    coef[2] * ((IN)[stencil_index + 2] + (IN)[stencil_index - 2] + \
                               (IN)[stencil_index + 2 * Nx] + (IN)[stencil_index - 2 * Nx] + \
                               (IN)[stencil_index + 2 * Nxy] + (IN)[stencil_index - 2 * Nxy]) + \
                    coef[3] * ((IN)[stencil_index + 3] + (IN)[stencil_index - 3] + \
                               (IN)[stencil_index + 3 * Nx] + (IN)[stencil_index - 3 * Nx] + \
                               (IN)[stencil_index + 3 * Nxy] + (IN)[stencil_index - 3 * Nxy]); \
        (OUT)[stencil_index] = 2 * (IN)[stencil_index] - (OUT)[stencil_index] + (V)[stencil_index] * div; \
    } while (0)

    for (int z = z0; z < z1; ++z) {
        for (int y = y0; y < y1; ++y) {
            const int row_base = z * Nxy + y * Nx;
            const int line_length = x1 - x0;
            if (line_length <= 0)
                continue;

            const float* line_in = Ain + row_base + x0;
            const float* line_vsq = vsq + row_base + x0;
            float* line_out = Aout + row_base + x0;
#if defined(_OPENMP) && _OPENMP >= 201307
            const std::uintptr_t alignment_mask = std::uintptr_t(31);
            const std::uintptr_t in_residue = reinterpret_cast<std::uintptr_t>(line_in) & alignment_mask;
            const std::uintptr_t vsq_residue = reinterpret_cast<std::uintptr_t>(line_vsq) & alignment_mask;
            const std::uintptr_t out_residue = reinterpret_cast<std::uintptr_t>(line_out) & alignment_mask;
            int peel = -1;
            if (in_residue == vsq_residue && in_residue == out_residue) {
                const std::uintptr_t peel_bytes = (std::uintptr_t(32) - in_residue) & alignment_mask;
                if (peel_bytes % sizeof(float) == 0)
                    peel = static_cast<int>(peel_bytes / sizeof(float));
            }

            if (peel >= 0 && peel <= line_length) {
                for (int i = 0; i < peel; ++i)
                    STENCIL_UPDATE(line_in, line_vsq, line_out, i);

                const float* aligned_in = line_in + peel;
                const float* aligned_vsq = line_vsq + peel;
                float* aligned_out = line_out + peel;
                const int aligned_length = line_length - peel;
#pragma omp simd aligned(aligned_in, aligned_vsq, aligned_out : 32)
                for (int i = 0; i < aligned_length; ++i)
                    STENCIL_UPDATE(aligned_in, aligned_vsq, aligned_out, i);
            } else {
#pragma omp simd
                for (int i = 0; i < line_length; ++i)
                    STENCIL_UPDATE(line_in, line_vsq, line_out, i);
            }
#else
            for (int i = 0; i < line_length; ++i)
                STENCIL_UPDATE(line_in, line_vsq, line_out, i);
#endif
        }
    }
#undef STENCIL_UPDATE
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

extern "C" void run(const void* input1, const void* input2, void* output, int n, int parameter, int threads) {
    size_t s = size_t(n) * n * n;
    const float* a = (const float*)input1;
    float* c = (float*)output;
    memcpy(c, a, s * 4);
    memset(c + s, 0, s * 4);
    const float co[4] = {.5f, -.25f, .125f, -.0625f};
    loop_stencil_serial(0, 6, 4, n - 4, 4, n - 4, 4, n - 4, n, n, n, co, (const float*)input2, c, c + s);
}
