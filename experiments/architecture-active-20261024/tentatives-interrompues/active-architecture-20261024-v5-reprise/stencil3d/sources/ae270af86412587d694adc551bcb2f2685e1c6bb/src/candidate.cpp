/*
  Copyright (c) 2010-2023, Intel Corporation

  SPDX-License-Identifier: BSD-3-Clause
*/

#include <cstddef>
#include <cstring>

static inline void stencil_row(int y, int z, int x0, int x1, int Nx, int Nxy, const float coef[4],
                               const float vsq[], const float Ain[], float Aout[]) {
    const int row_index = z * Nxy + y * Nx;
    for (int x = x0; x < x1; ++x) {
        const int index = row_index + x;
        const float div = coef[0] * Ain[index] +
                          coef[1] * (Ain[index + 1] + Ain[index - 1] + Ain[index + Nx] + Ain[index - Nx] +
                                     Ain[index + Nxy] + Ain[index - Nxy]) +
                          coef[2] * (Ain[index + 2] + Ain[index - 2] + Ain[index + 2 * Nx] +
                                     Ain[index - 2 * Nx] + Ain[index + 2 * Nxy] + Ain[index - 2 * Nxy]) +
                          coef[3] * (Ain[index + 3] + Ain[index - 3] + Ain[index + 3 * Nx] +
                                     Ain[index - 3 * Nx] + Ain[index + 3 * Nxy] + Ain[index - 3 * Nxy]);
        Aout[index] = 2 * Ain[index] - Aout[index] + vsq[index] * div;
    }
}

static void stencil_step(int x0, int x1, int y0, int y1, int z0, int z1, int Nx, int Ny,
                         const float coef[4], const float vsq[], const float Ain[], float Aout[]) {
    const int Nxy = Nx * Ny;
    for (int z = z0; z < z1; ++z) {
        for (int y = y0; y < y1; ++y) {
            stencil_row(y, z, x0, x1, Nx, Nxy, coef, vsq, Ain, Aout);
        }
    }
}

static void stencil_step_parallel(int x0, int x1, int y0, int y1, int z0, int z1, int Nx, int Ny,
                                  int threads, const float coef[4], const float vsq[], const float Ain[],
                                  float Aout[]) {
    if (x1 <= x0 || y1 <= y0 || z1 <= z0) {
        return;
    }

    const std::size_t z_count = static_cast<std::size_t>(z1 - z0);
    const std::size_t y_count = static_cast<std::size_t>(y1 - y0);
    const std::size_t requested = static_cast<std::size_t>(threads);
    int worker_count = threads;
    if (y_count <= (requested - 1) / z_count) {
        worker_count = static_cast<int>(z_count * y_count);
    }

    const int Nxy = Nx * Ny;
#pragma omp parallel for collapse(2) schedule(static) num_threads(worker_count)
    for (int z = z0; z < z1; ++z) {
        for (int y = y0; y < y1; ++y) {
            stencil_row(y, z, x0, x1, Nx, Nxy, coef, vsq, Ain, Aout);
        }
    }
}

void loop_stencil_serial(int t0, int t1, int x0, int x1, int y0, int y1, int z0, int z1, int Nx, int Ny,
                         int Nz, const float coef[4], const float vsq[], float Aeven[], float Aodd[]) {
    for (int t = t0; t < t1; ++t) {
        if ((t & 1) == 0)
            stencil_step(x0, x1, y0, y1, z0, z1, Nx, Ny, coef, vsq, Aeven, Aodd);
        else
            stencil_step(x0, x1, y0, y1, z0, z1, Nx, Ny, coef, vsq, Aodd, Aeven);
    }
}

static void loop_stencil_parallel_steps(int t0, int t1, int x0, int x1, int y0, int y1, int z0, int z1,
                                        int Nx, int Ny, int threads, const float coef[4], const float vsq[],
                                        float Aeven[], float Aodd[]) {
    for (int t = t0; t < t1; ++t) {
        if ((t & 1) == 0)
            stencil_step_parallel(x0, x1, y0, y1, z0, z1, Nx, Ny, threads, coef, vsq, Aeven, Aodd);
        else
            stencil_step_parallel(x0, x1, y0, y1, z0, z1, Nx, Ny, threads, coef, vsq, Aodd, Aeven);
    }
}

extern "C" void run(const void* input1, const void* input2, void* output, int n, int parameter, int threads) {
    const std::size_t s = static_cast<std::size_t>(n) * n * n;
    const float* a = static_cast<const float*>(input1);
    float* c = static_cast<float*>(output);
    std::memcpy(c, a, s * sizeof(float));
    std::memset(c + s, 0, s * sizeof(float));
    const float co[4] = {0.5f, -0.25f, 0.125f, -0.0625f};
    const float* vsq = static_cast<const float*>(input2);

    const int x0 = 4;
    const int x1 = n - 4;
    const int y0 = 4;
    const int y1 = n - 4;
    const int z0 = 4;
    const int z1 = n - 4;
    const std::size_t active_width = n > 8 ? static_cast<std::size_t>(n - 8) : 0;

    // Keep the serial baseline for one-thread and small-work calls. For larger
    // budgets, each timestep gets a static row-level OpenMP region.
    if (threads > 1 && active_width >= 16) {
        loop_stencil_parallel_steps(0, 6, x0, x1, y0, y1, z0, z1, n, n, threads, co, vsq, c, c + s);
    } else {
        loop_stencil_serial(0, 6, x0, x1, y0, y1, z0, z1, n, n, n, co, vsq, c, c + s);
    }
}
