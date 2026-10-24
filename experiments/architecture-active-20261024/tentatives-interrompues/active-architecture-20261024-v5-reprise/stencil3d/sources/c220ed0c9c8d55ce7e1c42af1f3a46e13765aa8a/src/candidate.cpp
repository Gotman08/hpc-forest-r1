/*
  Copyright (c) 2010-2023, Intel Corporation

  SPDX-License-Identifier: BSD-3-Clause
*/

#include <algorithm>
#include <cstddef>
#include <cstdlib>
#include <cstring>

static void stencil_step(int x0, int x1, int y0, int y1, int z0, int z1, int Nx, int Ny, int Nz, const float coef[4],
                         const float vsq[], const float Ain[], const float Aprev[], float Aout[]) {
    int Nxy = Nx * Ny;

    for (int z = z0; z < z1; ++z) {
        for (int y = y0; y < y1; ++y) {
            for (int x = x0; x < x1; ++x) {
                int index = (z * Nxy) + (y * Nx) + x;
#define A_cur(x, y, z) Ain[index + (x) + ((y)*Nx) + ((z)*Nxy)]
                float div = coef[0] * A_cur(0, 0, 0) +
                            coef[1] * (A_cur(+1, 0, 0) + A_cur(-1, 0, 0) + A_cur(0, +1, 0) + A_cur(0, -1, 0) +
                                       A_cur(0, 0, +1) + A_cur(0, 0, -1)) +
                            coef[2] * (A_cur(+2, 0, 0) + A_cur(-2, 0, 0) + A_cur(0, +2, 0) + A_cur(0, -2, 0) +
                                       A_cur(0, 0, +2) + A_cur(0, 0, -2)) +
                            coef[3] * (A_cur(+3, 0, 0) + A_cur(-3, 0, 0) + A_cur(0, +3, 0) + A_cur(0, -3, 0) +
                                       A_cur(0, 0, +3) + A_cur(0, 0, -3));

                Aout[index] = 2 * A_cur(0, 0, 0) - Aprev[index] + vsq[index] * div;
#undef A_cur
            }
        }
    }
}

static void stencil_triplet_temporal_tiles(int Nx, int Ny, int Nz, const float coef[4], const float vsq[],
                                           float current[], float previous[], float old_current[],
                                           float old_previous[], float first[], float second[], std::size_t bytes) {
    const int block = 32;
    const int radius = 3;
    const int full_halo = 2 * radius;

    // Snapshot both time levels so tiles never consume values written by another tile.
    // Initialize the intermediate grids to preserve each buffer's untouched boundary.
    std::memcpy(old_current, current, bytes);
    std::memcpy(old_previous, previous, bytes);
    std::memcpy(first, previous, bytes);
    std::memcpy(second, current, bytes);

    for (int z0 = 4; z0 < Nz - 4; z0 += block) {
        const int z1 = std::min(z0 + block, Nz - 4);
        for (int y0 = 4; y0 < Ny - 4; y0 += block) {
            const int y1 = std::min(y0 + block, Ny - 4);
            for (int x0 = 4; x0 < Nx - 4; x0 += block) {
                const int x1 = std::min(x0 + block, Nx - 4);

                // Three fused steps require first-step values out to radius 6,
                // second-step values out to radius 3, and then the tile core.
                const int x2_0 = std::max(x0 - full_halo, 4);
                const int x2_1 = std::min(x1 + full_halo, Nx - 4);
                const int y2_0 = std::max(y0 - full_halo, 4);
                const int y2_1 = std::min(y1 + full_halo, Ny - 4);
                const int z2_0 = std::max(z0 - full_halo, 4);
                const int z2_1 = std::min(z1 + full_halo, Nz - 4);

                const int x1_0 = std::max(x0 - radius, 4);
                const int x1_1 = std::min(x1 + radius, Nx - 4);
                const int y1_0 = std::max(y0 - radius, 4);
                const int y1_1 = std::min(y1 + radius, Ny - 4);
                const int z1_0 = std::max(z0 - radius, 4);
                const int z1_1 = std::min(z1 + radius, Nz - 4);

                // Levels t+1 and t+2 are computed in scratch; the third step
                // writes the disjoint core to the buffer for level t+3.
                stencil_step(x2_0, x2_1, y2_0, y2_1, z2_0, z2_1, Nx, Ny, Nz, coef, vsq,
                             old_current, old_previous, first);
                stencil_step(x1_0, x1_1, y1_0, y1_1, z1_0, z1_1, Nx, Ny, Nz, coef, vsq,
                             first, old_current, second);
                stencil_step(x0, x1, y0, y1, z0, z1, Nx, Ny, Nz, coef, vsq,
                             second, first, previous);
            }
        }
    }

    // After three steps, previous holds level t+3 and second holds level t+2.
    std::memcpy(current, second, bytes);
}

static void stencil_step_full(int Nx, int Ny, int Nz, const float coef[4], const float vsq[], const float Ain[],
                              const float Aprev[], float Aout[]) {
    stencil_step(4, Nx - 4, 4, Ny - 4, 4, Nz - 4, Nx, Ny, Nz, coef, vsq, Ain, Aprev, Aout);
}

void loop_stencil_serial(int t0, int t1, int x0, int x1, int y0, int y1, int z0, int z1, int Nx, int Ny, int Nz,
                         const float coef[4], const float vsq[], float Aeven[], float Aodd[]) {
    for (int t = t0; t < t1; ++t) {
        if ((t & 1) == 0)
            stencil_step(x0, x1, y0, y1, z0, z1, Nx, Ny, Nz, coef, vsq, Aeven, Aodd, Aodd);
        else
            stencil_step(x0, x1, y0, y1, z0, z1, Nx, Ny, Nz, coef, vsq, Aodd, Aeven, Aeven);
    }
}

extern "C" void run(const void* input1, const void* input2, void* output, int n, int parameter, int threads) {
    (void)parameter;
    (void)threads;

    const std::size_t side = static_cast<std::size_t>(n);
    const std::size_t volume = side * side * side;
    const std::size_t bytes = volume * sizeof(float);
    const float* input = static_cast<const float*>(input1);
    const float* vsq = static_cast<const float*>(input2);
    float* even = static_cast<float*>(output);
    float* odd = even + volume;

    std::memcpy(even, input, bytes);
    std::memset(odd, 0, bytes);

    const float coef[4] = {0.5f, -0.25f, 0.125f, -0.0625f};
    float* old_current = static_cast<float*>(std::malloc(bytes));
    float* old_previous = static_cast<float*>(std::malloc(bytes));
    float* first = static_cast<float*>(std::malloc(bytes));
    float* second = static_cast<float*>(std::malloc(bytes));
    if (old_current == nullptr || old_previous == nullptr || first == nullptr || second == nullptr) {
        std::free(old_current);
        std::free(old_previous);
        std::free(first);
        std::free(second);
        loop_stencil_serial(0, 6, 4, n - 4, 4, n - 4, 4, n - 4, n, n, n, coef, vsq, even, odd);
        return;
    }

    for (int t = 0; t < 6; t += 3) {
        // Each triplet alternates buffer roles according to its starting parity.
        float* current = ((t & 1) == 0) ? even : odd;
        float* previous = ((t & 1) == 0) ? odd : even;
        stencil_triplet_temporal_tiles(n, n, n, coef, vsq, current, previous, old_current, old_previous,
                                       first, second, bytes);
    }

    std::free(old_current);
    std::free(old_previous);
    std::free(first);
    std::free(second);
}
