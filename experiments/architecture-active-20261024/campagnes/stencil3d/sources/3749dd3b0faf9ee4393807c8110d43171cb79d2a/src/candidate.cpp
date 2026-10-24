/*
  Copyright (c) 2010-2023, Intel Corporation

  SPDX-License-Identifier: BSD-3-Clause
*/

#include <cstddef>
#include <cstring>
#include <omp.h>

static void loop_stencil_persistent_static(int t0, int t1, int x0, int x1, int y0, int y1, int z0, int z1,
                                           int Nx, int Ny, const float coef[4], const float vsq[],
                                           float Aeven[], float Aodd[], int threads) {
    if (t0 >= t1 || x0 >= x1 || y0 >= y1 || z0 >= z1)
        return;

    const std::size_t y_count = static_cast<std::size_t>(y1 - y0);
    const std::size_t row_count = static_cast<std::size_t>(z1 - z0) * y_count;
    int requested_threads = threads > 0 ? threads : 1;
    if (row_count < static_cast<std::size_t>(requested_threads))
        requested_threads = static_cast<int>(row_count);

    const std::ptrdiff_t plane_stride = static_cast<std::ptrdiff_t>(Nx) * Ny;
    const std::ptrdiff_t row_stride = Nx;

#pragma omp parallel num_threads(requested_threads) shared(t0, t1, x0, x1, y0, z0, Nx, Ny, coef, vsq, Aeven, Aodd, row_count, y_count, plane_stride, row_stride)
    {
        const int thread_id = omp_get_thread_num();
        const std::size_t team_size = static_cast<std::size_t>(omp_get_num_threads());
        const std::size_t chunk = row_count / team_size;
        const std::size_t remainder = row_count % team_size;
        const std::size_t row_begin = static_cast<std::size_t>(thread_id) * chunk +
                                      (static_cast<std::size_t>(thread_id) < remainder ? thread_id : remainder);
        const std::size_t row_end = row_begin + chunk + (static_cast<std::size_t>(thread_id) < remainder ? 1 : 0);

        for (int t = t0; t < t1; ++t) {
            const float* Ain = (t & 1) == 0 ? Aeven : Aodd;
            float* Aout = (t & 1) == 0 ? Aodd : Aeven;

            for (std::size_t row = row_begin; row < row_end; ++row) {
                const int z = z0 + static_cast<int>(row / y_count);
                const int y = y0 + static_cast<int>(row % y_count);
                const std::ptrdiff_t row_base = static_cast<std::ptrdiff_t>(z) * plane_stride +
                                                static_cast<std::ptrdiff_t>(y) * row_stride;

                for (int x = x0; x < x1; ++x) {
                    const std::ptrdiff_t index = row_base + x;
                    const float* center = Ain + index;
                    float* next = Aout + index;
                    const float div = coef[0] * center[0] +
                                     coef[1] * (center[1] + center[-1] + center[row_stride] + center[-row_stride] +
                                                center[plane_stride] + center[-plane_stride]) +
                                     coef[2] * (center[2] + center[-2] + center[2 * row_stride] +
                                                center[-2 * row_stride] + center[2 * plane_stride] +
                                                center[-2 * plane_stride]) +
                                     coef[3] * (center[3] + center[-3] + center[3 * row_stride] +
                                                center[-3 * row_stride] + center[3 * plane_stride] +
                                                center[-3 * plane_stride]);
                    next[0] = 2 * center[0] - next[0] + vsq[index] * div;
                }
            }

            // Each thread completes its rows before any thread starts the next timestep.
#pragma omp barrier
        }
    }
}

extern "C" void run(const void* input1, const void* input2, void* output, int n, int parameter, int threads) {
    (void)parameter;
    const std::size_t volume = static_cast<std::size_t>(n) * n * n;
    const float* initial = static_cast<const float*>(input1);
    float* even = static_cast<float*>(output);
    float* odd = even + volume;

    std::memcpy(even, initial, volume * sizeof(float));
    std::memset(odd, 0, volume * sizeof(float));

    const float coef[4] = {0.5f, -0.25f, 0.125f, -0.0625f};
    loop_stencil_persistent_static(0, 6, 4, n - 4, 4, n - 4, 4, n - 4, n, n, coef,
                                   static_cast<const float*>(input2), even, odd, threads);
}
