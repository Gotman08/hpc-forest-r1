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

static void stencil_step(int x0, int x1, int y0, int y1, int z0, int z1, int Nx, int Ny,
                         const float* STENCIL_RESTRICT coef, const float* STENCIL_RESTRICT vsq,
                         const float* STENCIL_RESTRICT Ain, float* STENCIL_RESTRICT Aout) {
    const int Nxy = Nx * Ny;

    for (int z = z0; z < z1; ++z) {
        const int zbase = z * Nxy;
        for (int y = y0; y < y1; ++y) {
            const int row_index = zbase + y * Nx + x0;
            const float* const in = Ain + row_index;
            const float* const velocity = vsq + row_index;
            float* const out = Aout + row_index;
#if defined(_OPENMP) && _OPENMP >= 201307
#pragma omp simd
#endif
            for (int x = x0; x < x1; ++x) {
                const int i = x - x0;
                const float center = in[i];
                const float div = coef[0] * center +
                                  coef[1] * (in[i + 1] + in[i - 1] + in[i + Nx] + in[i - Nx] +
                                             in[i + Nxy] + in[i - Nxy]) +
                                  coef[2] * (in[i + 2] + in[i - 2] + in[i + 2 * Nx] + in[i - 2 * Nx] +
                                             in[i + 2 * Nxy] + in[i - 2 * Nxy]) +
                                  coef[3] * (in[i + 3] + in[i - 3] + in[i + 3 * Nx] + in[i - 3 * Nx] +
                                             in[i + 3 * Nxy] + in[i - 3 * Nxy]);

                out[i] = 2 * center - out[i] + velocity[i] * div;
            }
        }
    }
}

#undef STENCIL_RESTRICT

static void loop_stencil_persistent(int t0, int t1, int x0, int x1, int y0, int y1, int z0, int z1,
                                    int Nx, int Ny, const float coef[4], const float vsq[],
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

            stencil_step(x0, x1, y0, y1, thread_z0, thread_z1, Nx, Ny, coef, vsq, current, next);

            if (t + 1 < t1) {
#pragma omp barrier
            }
        }
    }
}

extern "C" void run(const void* input1, const void* input2, void* output, int n, int parameter, int threads) {
    (void)parameter;

    const std::size_t count = static_cast<std::size_t>(n) * n * n;
    const float* const initial = static_cast<const float*>(input1);
    float* const even = static_cast<float*>(output);
    float* const odd = even + count;

    std::memcpy(even, initial, count * sizeof(float));
    std::memset(odd, 0, count * sizeof(float));

    const float coef[4] = {0.5f, -0.25f, 0.125f, -0.0625f};
    loop_stencil_persistent(0, 6, 4, n - 4, 4, n - 4, 4, n - 4, n, n, coef,
                            static_cast<const float*>(input2), even, odd, threads);
}
