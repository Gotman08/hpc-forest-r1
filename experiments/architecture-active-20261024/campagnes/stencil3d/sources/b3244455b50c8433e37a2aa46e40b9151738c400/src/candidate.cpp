/*
  Copyright (c) 2010-2023, Intel Corporation

  SPDX-License-Identifier: BSD-3-Clause
*/

#include <algorithm>
#include <cstddef>
#include <cstring>
#include <omp.h>

extern "C" void run(const void* input1, const void* input2, void* output, int n, int parameter, int threads) {
    (void)parameter;

    const std::size_t count = static_cast<std::size_t>(n) * n * n;
    const float* initial = static_cast<const float*>(input1);
    const float* velocity_sq = static_cast<const float*>(input2);
    float* first = static_cast<float*>(output);
    float* second = first + count;

    std::memcpy(first, initial, count * sizeof(float));
    std::memset(second, 0, count * sizeof(float));

    const int interior_z = n > 8 ? n - 8 : 0;
    const int requested_threads = threads > 0 ? threads : 1;
    const int team_size = std::min(requested_threads, std::max(interior_z, 1));
    const int nxy = n * n;
    const float coef[4] = {0.5f, -0.25f, 0.125f, -0.0625f};

    // Keep each thread on the same contiguous z-slab for all timesteps.
    #pragma omp parallel num_threads(team_size)
    {
        const int thread_id = omp_get_thread_num();
        const int actual_threads = omp_get_num_threads();
        const int slices_per_thread = interior_z / actual_threads;
        const int extra_slices = interior_z % actual_threads;
        const int z0 = 4 + thread_id * slices_per_thread + std::min(thread_id, extra_slices);
        const int z1 = z0 + slices_per_thread + (thread_id < extra_slices ? 1 : 0);

        for (int t = 0; t < 6; ++t) {
            const float* current = (t & 1) == 0 ? first : second;
            float* next = (t & 1) == 0 ? second : first;

            for (int z = z0; z < z1; ++z) {
                for (int y = 4; y < n - 4; ++y) {
                    for (int x = 4; x < n - 4; ++x) {
                        const int index = z * nxy + y * n + x;
                        const float center = current[index];
                        const float div =
                            coef[0] * center +
                            coef[1] * (current[index + 1] + current[index - 1] + current[index + n] +
                                       current[index - n] + current[index + nxy] + current[index - nxy]) +
                            coef[2] * (current[index + 2] + current[index - 2] + current[index + 2 * n] +
                                       current[index - 2 * n] + current[index + 2 * nxy] + current[index - 2 * nxy]) +
                            coef[3] * (current[index + 3] + current[index - 3] + current[index + 3 * n] +
                                       current[index - 3 * n] + current[index + 3 * nxy] + current[index - 3 * nxy]);

                        next[index] = 2 * center - next[index] + velocity_sq[index] * div;
                    }
                }
            }

            // The team-end barrier completes the final step; synchronize only between dependent steps.
            if (t != 5) {
                #pragma omp barrier
            }
        }
    }
}
