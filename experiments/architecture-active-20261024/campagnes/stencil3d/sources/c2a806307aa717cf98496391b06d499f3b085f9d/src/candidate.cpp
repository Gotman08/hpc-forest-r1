/*
  Copyright (c) 2010-2023, Intel Corporation

  SPDX-License-Identifier: BSD-3-Clause
*/

#include <algorithm>
#include <cstddef>
#include <cstring>
#include <omp.h>

#if defined(__GNUC__) || defined(__clang__)
#define STENCIL_RESTRICT __restrict__
#else
#define STENCIL_RESTRICT
#endif

static void stencil_step(int x0, int x1, int y0, int y1, int z0, int z1, int Nx, int Ny, int Nz,
                         const float* STENCIL_RESTRICT coef, const float* STENCIL_RESTRICT vsq,
                         const float* STENCIL_RESTRICT Ain, float* STENCIL_RESTRICT Aout) {
    const int Nxy = Nx * Ny;

    for (int z = z0; z < z1; ++z) {
        const int zbase = z * Nxy;
        for (int y = y0; y < y1; ++y) {
            const int row = zbase + y * Nx;
            const float* const in_row = Ain + row;
            const float* const vsq_row = vsq + row;
            float* const out_row = Aout + row;
            for (int x = x0; x < x1; ++x) {
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

static void loop_stencil_parallel(int t0, int t1, int x0, int x1, int y0, int y1, int z0, int z1,
                                  int Nx, int Ny, int Nz, const float coef[4], const float vsq[],
                                  float Aeven[], float Aodd[], int threads) {
    const int interior_z = z1 > z0 ? z1 - z0 : 0;
    const int requested_threads = threads > 0 ? threads : 1;
    const int team_size = std::min(requested_threads, std::max(interior_z, 1));

    #pragma omp parallel num_threads(team_size)
    {
        const int thread_id = omp_get_thread_num();
        const int actual_threads = omp_get_num_threads();
        const int slices_per_thread = interior_z / actual_threads;
        const int extra_slices = interior_z % actual_threads;
        const int thread_z0 = z0 + thread_id * slices_per_thread + std::min(thread_id, extra_slices);
        const int thread_z1 = thread_z0 + slices_per_thread + (thread_id < extra_slices ? 1 : 0);

        for (int t = t0; t < t1; ++t) {
            const float* current = (t & 1) == 0 ? Aeven : Aodd;
            float* next = (t & 1) == 0 ? Aodd : Aeven;

            stencil_step(x0, x1, y0, y1, thread_z0, thread_z1, Nx, Ny, Nz, coef, vsq, current, next);

            if (t + 1 < t1) {
                #pragma omp barrier
            }
        }
    }
}

extern "C" void run(const void* input1, const void* input2, void* output, int n, int parameter, int threads) {
    (void)parameter;

    const std::size_t count = static_cast<std::size_t>(n) * n * n;
    const float* initial = static_cast<const float*>(input1);
    float* first = static_cast<float*>(output);
    float* second = first + count;

    std::memcpy(first, initial, count * sizeof(float));
    std::memset(second, 0, count * sizeof(float));

    const float coef[4] = {0.5f, -0.25f, 0.125f, -0.0625f};
    loop_stencil_parallel(0, 6, 4, n - 4, 4, n - 4, 4, n - 4, n, n, n,
                          coef, static_cast<const float*>(input2), first, second, threads);
}
