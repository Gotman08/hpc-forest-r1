#include <algorithm>
#include <cstddef>
#include <cstring>
#include <omp.h>

extern "C" void run(const void* input1, const void* input2, void* output,
                    int n, int parameter, int threads) {
    (void)parameter;
    if (n <= 0) {
        return;
    }

    const std::size_t size = static_cast<std::size_t>(n);
    const float* a = static_cast<const float*>(input1);
    const float* b = static_cast<const float*>(input2);
    float* c = static_cast<float*>(output);

    // Preserve overwrite behavior on every invocation.
    std::memset(c, 0, size * size * sizeof(float));

    constexpr int rows_per_tile = 8;
    const int tile_count = n / rows_per_tile + (n % rows_per_tile != 0);
    const int worker_count = threads > 1 ? std::min(threads, tile_count) : 1;

    #pragma omp parallel for schedule(static) num_threads(worker_count) if(worker_count > 1)
    for (int tile = 0; tile < tile_count; ++tile) {
        const int row_begin = tile * rows_per_tile;
        const int rows_in_tile = std::min(rows_per_tile, n - row_begin);

        for (int k = 0; k < n; ++k) {
            const float* b_row = b + static_cast<std::size_t>(k) * size;
            for (int row_offset = 0; row_offset < rows_in_tile; ++row_offset) {
                const int r = row_begin + row_offset;
                const float a_value = a[static_cast<std::size_t>(r) * size +
                                        static_cast<std::size_t>(k)];
                float* c_row = c + static_cast<std::size_t>(r) * size;
                for (int col = 0; col < n; ++col) {
                    c_row[col] += a_value * b_row[col];
                }
            }
        }
    }
}
