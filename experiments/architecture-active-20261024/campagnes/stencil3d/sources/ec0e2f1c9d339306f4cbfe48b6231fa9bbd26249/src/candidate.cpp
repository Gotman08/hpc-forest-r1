#include <algorithm>
#include <cstddef>
#include <cstring>
#include <memory>
#include <omp.h>

extern "C" void run(const void* input1, const void* input2, void* output, int n, int parameter, int threads) {
    const std::size_t size = static_cast<std::size_t>(n) * n * n;
    const float* input = static_cast<const float*>(input1);
    const float* vsq = static_cast<const float*>(input2);
    float* even = static_cast<float*>(output);
    float* odd = even + size;

    std::memcpy(even, input, size * sizeof(float));
    std::memset(odd, 0, size * sizeof(float));
    (void)parameter;

    constexpr int radius = 3;
    constexpr int steps = 6;
    constexpr int halo = radius * steps;
    constexpr int tile = 64;
    constexpr int interior_begin = 4;
    const int interior_end = n - 4;
    const int interior_size = interior_end - interior_begin;
    if (interior_size <= 0) return;

    const int tiles_x = (interior_size + tile - 1) / tile;
    const int tiles_y = tiles_x;
    const int tiles_z = tiles_x;
    const int worker_count = threads > 0 ? threads : 1;
    const int max_side = std::min(n, tile + 2 * halo);
    const std::size_t max_volume = static_cast<std::size_t>(max_side) * max_side * max_side;
    const float coef[4] = {0.5f, -0.25f, 0.125f, -0.0625f};

#pragma omp parallel num_threads(worker_count)
    {
        std::unique_ptr<float[]> even_scratch(new float[max_volume]);
        std::unique_ptr<float[]> odd_scratch(new float[max_volume]);

#pragma omp for collapse(3) schedule(static)
        for (int tz = 0; tz < tiles_z; ++tz) {
            for (int ty = 0; ty < tiles_y; ++ty) {
                for (int tx = 0; tx < tiles_x; ++tx) {
                    const int x0 = interior_begin + tx * tile;
                    const int y0 = interior_begin + ty * tile;
                    const int z0 = interior_begin + tz * tile;
                    const int x1 = std::min(x0 + tile, interior_end);
                    const int y1 = std::min(y0 + tile, interior_end);
                    const int z1 = std::min(z0 + tile, interior_end);

                    const int sx0 = std::max(0, x0 - halo);
                    const int sy0 = std::max(0, y0 - halo);
                    const int sz0 = std::max(0, z0 - halo);
                    const int sx1 = std::min(n, x1 + halo);
                    const int sy1 = std::min(n, y1 + halo);
                    const int sz1 = std::min(n, z1 + halo);
                    const int lx = sx1 - sx0;
                    const int ly = sy1 - sy0;
                    const std::size_t volume = static_cast<std::size_t>(lx) * ly * (sz1 - sz0);
                    const std::ptrdiff_t plane = static_cast<std::ptrdiff_t>(lx) * ly;

                    std::fill(odd_scratch.get(), odd_scratch.get() + volume, 0.0f);
                    for (int z = sz0; z < sz1; ++z) {
                        for (int y = sy0; y < sy1; ++y) {
                            const std::size_t global_row = (static_cast<std::size_t>(z) * n + y) * n + sx0;
                            const std::size_t local_row = (static_cast<std::size_t>(z - sz0) * ly + (y - sy0)) * lx;
                            std::memcpy(even_scratch.get() + local_row, input + global_row,
                                        static_cast<std::size_t>(lx) * sizeof(float));
                        }
                    }

                    float* current = even_scratch.get();
                    float* next = odd_scratch.get();
                    for (int step = 0; step < steps; ++step) {
                        const int margin = radius * (steps - 1 - step);
                        const int ax0 = std::max(interior_begin, x0 - margin);
                        const int ay0 = std::max(interior_begin, y0 - margin);
                        const int az0 = std::max(interior_begin, z0 - margin);
                        const int ax1 = std::min(interior_end, x1 + margin);
                        const int ay1 = std::min(interior_end, y1 + margin);
                        const int az1 = std::min(interior_end, z1 + margin);

                        for (int z = az0; z < az1; ++z) {
                            for (int y = ay0; y < ay1; ++y) {
                                const std::size_t local_row = (static_cast<std::size_t>(z - sz0) * ly + (y - sy0)) * lx;
                                std::size_t global_index = (static_cast<std::size_t>(z) * n + y) * n + ax0;
                                for (int x = ax0; x < ax1; ++x, ++global_index) {
                                    const std::size_t local_index = local_row + (x - sx0);
                                    const float* center_ptr = current + local_index;
                                    const float center = center_ptr[0];
                                    const float div = coef[0] * center +
                                        coef[1] * (center_ptr[1] + center_ptr[-1] + center_ptr[lx] + center_ptr[-lx] +
                                                   center_ptr[plane] + center_ptr[-plane]) +
                                        coef[2] * (center_ptr[2] + center_ptr[-2] + center_ptr[2 * lx] + center_ptr[-2 * lx] +
                                                   center_ptr[2 * plane] + center_ptr[-2 * plane]) +
                                        coef[3] * (center_ptr[3] + center_ptr[-3] + center_ptr[3 * lx] + center_ptr[-3 * lx] +
                                                   center_ptr[3 * plane] + center_ptr[-3 * plane]);
                                    next[local_index] = 2.0f * center - next[local_index] + vsq[global_index] * div;
                                }
                            }
                        }
                        std::swap(current, next);
                    }

                    for (int z = z0; z < z1; ++z) {
                        for (int y = y0; y < y1; ++y) {
                            const std::size_t global_row = (static_cast<std::size_t>(z) * n + y) * n + x0;
                            const std::size_t local_row = (static_cast<std::size_t>(z - sz0) * ly + (y - sy0)) * lx + (x0 - sx0);
                            const std::size_t width = static_cast<std::size_t>(x1 - x0);
                            std::memcpy(even + global_row, current + local_row, width * sizeof(float));
                            std::memcpy(odd + global_row, next + local_row, width * sizeof(float));
                        }
                    }
                }
            }
        }
    }
}