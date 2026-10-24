/*
  Copyright (c) 2010-2023, Intel Corporation

  SPDX-License-Identifier: BSD-3-Clause
*/

#include <cstddef>
#include <cstdint>
#include <cstring>
#include <omp.h>

static void stencil_step(int x0, int x1, int y0, int y1, int z0, int z1, int Nx, int Ny, int Nz, const float coef[4],
                         const float vsq[], const float Ain[], float Aout[]) {
    const int Nxy = Nx * Ny;
    const int row_length = x1 - x0;
    constexpr std::uintptr_t alignment = 64;
    constexpr std::uintptr_t alignment_mask = alignment - 1;

    for (int z = z0; z < z1; ++z) {
        for (int y = y0; y < y1; ++y) {
            const int row_start = z * Nxy + y * Nx + x0;
            const float* in_line = Ain + row_start;
            const float* vsq_line = vsq + row_start;
            float* out_line = Aout + row_start;

            const std::uintptr_t in_residue = reinterpret_cast<std::uintptr_t>(in_line) & alignment_mask;
            const bool common_residue =
                (reinterpret_cast<std::uintptr_t>(vsq_line) & alignment_mask) == in_residue &&
                (reinterpret_cast<std::uintptr_t>(out_line) & alignment_mask) == in_residue;
            const int aligned_prefix =
                static_cast<int>(((alignment - in_residue) & alignment_mask) / sizeof(float));
            const bool use_aligned_loop = common_residue && aligned_prefix <= row_length;
            const int prefix = use_aligned_loop ? aligned_prefix : 0;

            for (int ix = 0; ix < prefix; ++ix) {
                const float center = in_line[ix];
                const float div = coef[0] * center +
                                  coef[1] * (in_line[ix + 1] + in_line[ix - 1] + in_line[ix + Nx] + in_line[ix - Nx] +
                                             in_line[ix + Nxy] + in_line[ix - Nxy]) +
                                  coef[2] * (in_line[ix + 2] + in_line[ix - 2] + in_line[ix + 2 * Nx] + in_line[ix - 2 * Nx] +
                                             in_line[ix + 2 * Nxy] + in_line[ix - 2 * Nxy]) +
                                  coef[3] * (in_line[ix + 3] + in_line[ix - 3] + in_line[ix + 3 * Nx] + in_line[ix - 3 * Nx] +
                                             in_line[ix + 3 * Nxy] + in_line[ix - 3 * Nxy]);
                out_line[ix] = 2 * center - out_line[ix] + vsq_line[ix] * div;
            }

            if (use_aligned_loop) {
                const float* in_vec = in_line + prefix;
                const float* vsq_vec = vsq_line + prefix;
                float* out_vec = out_line + prefix;
#if defined(_OPENMP) && _OPENMP >= 201307
#pragma omp simd aligned(in_vec, vsq_vec, out_vec : 64)
#endif
                for (int ix = 0; ix < row_length - prefix; ++ix) {
                    const float center = in_vec[ix];
                    const float div = coef[0] * center +
                                      coef[1] * (in_vec[ix + 1] + in_vec[ix - 1] + in_vec[ix + Nx] + in_vec[ix - Nx] +
                                                 in_vec[ix + Nxy] + in_vec[ix - Nxy]) +
                                      coef[2] * (in_vec[ix + 2] + in_vec[ix - 2] + in_vec[ix + 2 * Nx] + in_vec[ix - 2 * Nx] +
                                                 in_vec[ix + 2 * Nxy] + in_vec[ix - 2 * Nxy]) +
                                      coef[3] * (in_vec[ix + 3] + in_vec[ix - 3] + in_vec[ix + 3 * Nx] + in_vec[ix - 3 * Nx] +
                                                 in_vec[ix + 3 * Nxy] + in_vec[ix - 3 * Nxy]);
                    out_vec[ix] = 2 * center - out_vec[ix] + vsq_vec[ix] * div;
                }
            } else {
#if defined(_OPENMP) && _OPENMP >= 201307
#pragma omp simd
#endif
                for (int ix = 0; ix < row_length; ++ix) {
                    const float center = in_line[ix];
                    const float div = coef[0] * center +
                                      coef[1] * (in_line[ix + 1] + in_line[ix - 1] + in_line[ix + Nx] + in_line[ix - Nx] +
                                                 in_line[ix + Nxy] + in_line[ix - Nxy]) +
                                      coef[2] * (in_line[ix + 2] + in_line[ix - 2] + in_line[ix + 2 * Nx] + in_line[ix - 2 * Nx] +
                                                 in_line[ix + 2 * Nxy] + in_line[ix - 2 * Nxy]) +
                                      coef[3] * (in_line[ix + 3] + in_line[ix - 3] + in_line[ix + 3 * Nx] + in_line[ix - 3 * Nx] +
                                                 in_line[ix + 3 * Nxy] + in_line[ix - 3 * Nxy]);
                    out_line[ix] = 2 * center - out_line[ix] + vsq_line[ix] * div;
                }
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

extern "C" void run(const void* input1, const void* input2, void* output, int n, int parameter, int threads) {
    const std::size_t s = std::size_t(n) * n * n;
    const float* a = static_cast<const float*>(input1);
    float* c = static_cast<float*>(output);
    std::memcpy(c, a, s * sizeof(float));
    std::memset(c + s, 0, s * sizeof(float));
    const float co[4] = {.5f, -.25f, .125f, -.0625f};
    loop_stencil_serial(0, 6, 4, n - 4, 4, n - 4, 4, n - 4, n, n, n, co,
                        static_cast<const float*>(input2), c, c + s);
}
