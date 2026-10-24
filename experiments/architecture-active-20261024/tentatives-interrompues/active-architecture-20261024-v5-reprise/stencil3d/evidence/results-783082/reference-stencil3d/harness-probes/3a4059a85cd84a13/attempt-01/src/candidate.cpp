#include <algorithm>
#include <cstddef>
#include <cstdint>
#include <cstring>
#include <cmath>
#include <memory>
#include <omp.h>

/*
  Copyright (c) 2010-2023, Intel Corporation

  SPDX-License-Identifier: BSD-3-Clause
*/

static void stencil_step(int x0, int x1, int y0, int y1, int z0, int z1, int Nx, int Ny, int Nz, const float coef[4],
                         const float vsq[], const float Ain[], float Aout[]) {
    int Nxy = Nx * Ny;

    for (int z = z0; z < z1; ++z) {
        for (int y = y0; y < y1; ++y) {
            for (int x = x0; x < x1; ++x) {
                int index = (z * Nxy) + (y * Nx) + x;
#define A_cur(x, y, z) Ain[index + (x) + ((y)*Nx) + ((z)*Nxy)]
#define A_next(x, y, z) Aout[index + (x) + ((y)*Nx) + ((z)*Nxy)]
                float div = coef[0] * A_cur(0, 0, 0) +
                            coef[1] * (A_cur(+1, 0, 0) + A_cur(-1, 0, 0) + A_cur(0, +1, 0) + A_cur(0, -1, 0) +
                                       A_cur(0, 0, +1) + A_cur(0, 0, -1)) +
                            coef[2] * (A_cur(+2, 0, 0) + A_cur(-2, 0, 0) + A_cur(0, +2, 0) + A_cur(0, -2, 0) +
                                       A_cur(0, 0, +2) + A_cur(0, 0, -2)) +
                            coef[3] * (A_cur(+3, 0, 0) + A_cur(-3, 0, 0) + A_cur(0, +3, 0) + A_cur(0, -3, 0) +
                                       A_cur(0, 0, +3) + A_cur(0, 0, -3));

                A_next(0, 0, 0) = 2 * A_cur(0, 0, 0) - A_next(0, 0, 0) + vsq[index] * div;
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

static inline float stencil_value(std::size_t index, std::size_t Nx, std::size_t Nxy, const float coef[4],
                                  const float vsq[], const float current[], const float previous[]) {
    float div = coef[0] * current[index] +
                coef[1] * (current[index + 1] + current[index - 1] + current[index + Nx] + current[index - Nx] +
                           current[index + Nxy] + current[index - Nxy]) +
                coef[2] * (current[index + 2] + current[index - 2] + current[index + 2 * Nx] +
                           current[index - 2 * Nx] + current[index + 2 * Nxy] + current[index - 2 * Nxy]) +
                coef[3] * (current[index + 3] + current[index - 3] + current[index + 3 * Nx] +
                           current[index - 3 * Nx] + current[index + 3 * Nxy] + current[index - 3 * Nxy]);
    return 2 * current[index] - previous[index] + vsq[index] * div;
}

/* Advance an even/odd pair while keeping each tile's old time levels immutable. */
static void stencil_pair_tiled(int n, std::size_t volume, int tileX, int tileY, int tileZ, const float coef[4],
                               const float vsq[], float current[], float previous[], float currentSnapshot[],
                               float previousSnapshot[], float tile[]) {
    const std::size_t Nx = static_cast<std::size_t>(n);
    const std::size_t Nxy = Nx * Nx;
    std::memcpy(currentSnapshot, current, volume * sizeof(float));
    std::memcpy(previousSnapshot, previous, volume * sizeof(float));

    for (int z0 = 4; z0 < n - 4; z0 += tileZ) {
        const int z1 = std::min(z0 + tileZ, n - 4);
        for (int y0 = 4; y0 < n - 4; y0 += tileY) {
            const int y1 = std::min(y0 + tileY, n - 4);
            for (int x0 = 4; x0 < n - 4; x0 += tileX) {
                const int x1 = std::min(x0 + tileX, n - 4);

                // The second step needs a radius-3 halo of first-step values.
                const int hx0 = x0 - 3;
                const int hx1 = x1 + 3;
                const int hy0 = y0 - 3;
                const int hy1 = y1 + 3;
                const int hz0 = z0 - 3;
                const int hz1 = z1 + 3;
                const int haloNx = hx1 - hx0;
                const int haloNy = hy1 - hy0;
                const std::size_t haloNxy = static_cast<std::size_t>(haloNx) * haloNy;

                for (int z = hz0; z < hz1; ++z) {
                    for (int y = hy0; y < hy1; ++y) {
                        for (int x = hx0; x < hx1; ++x) {
                            const std::size_t globalIndex = static_cast<std::size_t>(z) * Nxy +
                                                            static_cast<std::size_t>(y) * Nx + x;
                            const std::size_t localIndex =
                                (static_cast<std::size_t>(z - hz0) * haloNy + (y - hy0)) * haloNx + (x - hx0);
                            const bool updated = x >= 4 && x < n - 4 && y >= 4 && y < n - 4 &&
                                                 z >= 4 && z < n - 4;
                            if (updated)
                                tile[localIndex] = stencil_value(globalIndex, Nx, Nxy, coef, vsq,
                                                                 currentSnapshot, previousSnapshot);
                            else
                                tile[localIndex] = previousSnapshot[globalIndex];
                        }
                    }
                }

                for (int z = z0; z < z1; ++z) {
                    for (int y = y0; y < y1; ++y) {
                        for (int x = x0; x < x1; ++x) {
                            const std::size_t globalIndex = static_cast<std::size_t>(z) * Nxy +
                                                            static_cast<std::size_t>(y) * Nx + x;
                            const std::size_t localIndex =
                                (static_cast<std::size_t>(z - hz0) * haloNy + (y - hy0)) * haloNx + (x - hx0);
                            const float mid = tile[localIndex];
                            const float div = coef[0] * mid +
                                              coef[1] * (tile[localIndex + 1] + tile[localIndex - 1] +
                                                         tile[localIndex + haloNx] + tile[localIndex - haloNx] +
                                                         tile[localIndex + haloNxy] + tile[localIndex - haloNxy]) +
                                              coef[2] * (tile[localIndex + 2] + tile[localIndex - 2] +
                                                         tile[localIndex + 2 * haloNx] + tile[localIndex - 2 * haloNx] +
                                                         tile[localIndex + 2 * haloNxy] + tile[localIndex - 2 * haloNxy]) +
                                              coef[3] * (tile[localIndex + 3] + tile[localIndex - 3] +
                                                         tile[localIndex + 3 * haloNx] + tile[localIndex - 3 * haloNx] +
                                                         tile[localIndex + 3 * haloNxy] + tile[localIndex - 3 * haloNxy]);
                            const float next = 2 * mid - currentSnapshot[globalIndex] + vsq[globalIndex] * div;
                            previous[globalIndex] = mid;
                            current[globalIndex] = next;
                        }
                    }
                }
            }
        }
    }
}

extern "C" void run(const void* input1, const void* input2, void* output, int n, int parameter, int threads) {
    const std::size_t volume = static_cast<std::size_t>(n) * n * n;
    const float* input = static_cast<const float*>(input1);
    float* outputBuffers = static_cast<float*>(output);
    std::memcpy(outputBuffers, input, volume * sizeof(float));
    std::memset(outputBuffers + volume, 0, volume * sizeof(float));

    const float coef[4] = {0.5f, -0.25f, 0.125f, -0.0625f};
    const float* vsq = static_cast<const float*>(input2);
    float* even = outputBuffers;
    float* odd = outputBuffers + volume;

    // A 64x64x32 core limits halo recomputation; allocation and snapshots are timed.
    const int tileX = 64;
    const int tileY = 64;
    const int tileZ = 32;
    const std::size_t tileElements = (static_cast<std::size_t>(tileX) + 6) *
                                     (static_cast<std::size_t>(tileY) + 6) *
                                     (static_cast<std::size_t>(tileZ) + 6);
    try {
        std::unique_ptr<float[]> currentSnapshot(new float[volume]);
        std::unique_ptr<float[]> previousSnapshot(new float[volume]);
        std::unique_ptr<float[]> tile(new float[tileElements]);
        for (int pair = 0; pair < 3; ++pair)
            stencil_pair_tiled(n, volume, tileX, tileY, tileZ, coef, vsq, even, odd,
                               currentSnapshot.get(), previousSnapshot.get(), tile.get());
    } catch (...) {
        loop_stencil_serial(0, 6, 4, n - 4, 4, n - 4, 4, n - 4, n, n, n,
                            coef, vsq, even, odd);
    }
}
