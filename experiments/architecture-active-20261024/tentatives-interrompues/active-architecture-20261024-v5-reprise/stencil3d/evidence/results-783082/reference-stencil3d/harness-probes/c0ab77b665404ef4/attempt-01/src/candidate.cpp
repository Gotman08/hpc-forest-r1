#include <cstddef>
#include <cstring>
#include <omp.h>

/*
  Copyright (c) 2010-2023, Intel Corporation

  SPDX-License-Identifier: BSD-3-Clause
*/

static inline void stencil_row(int y, int z, int x0, int x1, int Nx, int Nxy, const float coef[4], const float vsq[],
                               const float Ain[], float Aout[]) {
    int row_start = z * Nxy + y * Nx + x0;
    const float* in_line = Ain + row_start;
    const float* vsq_line = vsq + row_start;
    float* out_line = Aout + row_start;

#if defined(_OPENMP) && _OPENMP >= 201307
#pragma omp simd
#endif
    for (int ix = 0; ix < x1 - x0; ++ix) {
        float center = in_line[ix];
        float div = coef[0] * center +
                    coef[1] * (in_line[ix + 1] + in_line[ix - 1] + in_line[ix + Nx] + in_line[ix - Nx] +
                               in_line[ix + Nxy] + in_line[ix - Nxy]) +
                    coef[2] * (in_line[ix + 2] + in_line[ix - 2] + in_line[ix + 2 * Nx] + in_line[ix - 2 * Nx] +
                               in_line[ix + 2 * Nxy] + in_line[ix - 2 * Nxy]) +
                    coef[3] * (in_line[ix + 3] + in_line[ix - 3] + in_line[ix + 3 * Nx] + in_line[ix - 3 * Nx] +
                               in_line[ix + 3 * Nxy] + in_line[ix - 3 * Nxy]);

        out_line[ix] = 2 * center - out_line[ix] + vsq_line[ix] * div;
    }
}

static void stencil_step_serial(int x0, int x1, int y0, int y1, int z0, int z1, int Nx, int Ny,
                                const float coef[4], const float vsq[], const float Ain[], float Aout[]) {
    int Nxy = Nx * Ny;
    for (int z = z0; z < z1; ++z) {
        for (int y = y0; y < y1; ++y) {
            stencil_row(y, z, x0, x1, Nx, Nxy, coef, vsq, Ain, Aout);
        }
    }
}

static void stencil_step_parallel(int x0, int x1, int y0, int y1, int z0, int z1, int Nx, int Ny,
                                  const float coef[4], const float vsq[], const float Ain[], float Aout[]) {
    int Nxy = Nx * Ny;
#pragma omp for collapse(2) schedule(static)
    for (int z = z0; z < z1; ++z) {
        for (int y = y0; y < y1; ++y) {
            stencil_row(y, z, x0, x1, Nx, Nxy, coef, vsq, Ain, Aout);
        }
    }
}

static void loop_stencil_serial(int t0, int t1, int x0, int x1, int y0, int y1, int z0, int z1, int Nx, int Ny,
                                const float coef[4], const float vsq[], float Aeven[], float Aodd[]) {
    for (int t = t0; t < t1; ++t) {
        if ((t & 1) == 0)
            stencil_step_serial(x0, x1, y0, y1, z0, z1, Nx, Ny, coef, vsq, Aeven, Aodd);
        else
            stencil_step_serial(x0, x1, y0, y1, z0, z1, Nx, Ny, coef, vsq, Aodd, Aeven);
    }
}

static void loop_stencil_parallel(int t0, int t1, int x0, int x1, int y0, int y1, int z0, int z1, int Nx, int Ny,
                                  int threads, const float coef[4], const float vsq[], float Aeven[], float Aodd[]) {
#pragma omp parallel num_threads(threads)
    {
        for (int t = t0; t < t1; ++t) {
            if ((t & 1) == 0)
                stencil_step_parallel(x0, x1, y0, y1, z0, z1, Nx, Ny, coef, vsq, Aeven, Aodd);
            else
                stencil_step_parallel(x0, x1, y0, y1, z0, z1, Nx, Ny, coef, vsq, Aodd, Aeven);
        }
    }
}

extern "C" void run(const void* input1, const void* input2, void* output, int n, int parameter, int threads) {
    std::size_t s = static_cast<std::size_t>(n) * n * n;
    const float* a = static_cast<const float*>(input1);
    float* c = static_cast<float*>(output);
    std::memcpy(c, a, s * sizeof(float));
    std::memset(c + s, 0, s * sizeof(float));

    const float co[4] = {.5f, -.25f, .125f, -.0625f};
    if (threads > 1)
        loop_stencil_parallel(0, 6, 4, n - 4, 4, n - 4, 4, n - 4, n, n, threads, co,
                              static_cast<const float*>(input2), c, c + s);
    else
        loop_stencil_serial(0, 6, 4, n - 4, 4, n - 4, 4, n - 4, n, n, co,
                            static_cast<const float*>(input2), c, c + s);
}
