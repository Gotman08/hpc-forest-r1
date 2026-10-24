#include <algorithm>
#include <cstddef>
#include <cstring>
#include <omp.h>

static void multiply_row_tile(const float* a, const float* b, float* c, int n,
                              int row_tile) {
    constexpr int ROW_TILE = 8;
    constexpr int K_TILE = 32;
    constexpr int COL_TILE = 64;

    const int row_begin = row_tile * ROW_TILE;
    const int row_end = std::min(row_begin + ROW_TILE, n);

    for (int kk = 0; kk < n; kk += K_TILE) {
        const int k_end = std::min(kk + K_TILE, n);
        for (int jj = 0; jj < n; jj += COL_TILE) {
            const int col_end = std::min(jj + COL_TILE, n);
            for (int i = row_begin; i < row_end; ++i) {
                const std::size_t row_offset =
                    static_cast<std::size_t>(i) * static_cast<std::size_t>(n);
                const float* a_row = a + row_offset;
                float* c_row = c + row_offset;
                for (int k = kk; k < k_end; ++k) {
                    const float aik = a_row[k];
                    const float* b_row = b +
                        static_cast<std::size_t>(k) * static_cast<std::size_t>(n);
                    for (int j = jj; j < col_end; ++j) {
                        c_row[j] += aik * b_row[j];
                    }
                }
            }
        }
    }
}

extern "C" void run(const void* input1, const void* input2, void* output,
                    int n, int parameter, int threads) {
    (void)parameter;
    float* c = static_cast<float*>(output);
    std::memset(c, 0, static_cast<std::size_t>(n) *
                       static_cast<std::size_t>(n) * sizeof(float));

    const float* a = static_cast<const float*>(input1);
    const float* b = static_cast<const float*>(input2);
    const int row_tiles = n / 8 + (n % 8 != 0);

    int worker_count = threads;
    if (worker_count < 1) worker_count = 1;
    if (worker_count > 8) worker_count = 8;

    if (n < 256 || worker_count == 1) {
        for (int tile_i = 0; tile_i < row_tiles; ++tile_i) {
            multiply_row_tile(a, b, c, n, tile_i);
        }
    } else {
        #pragma omp parallel for schedule(static) num_threads(worker_count)
        for (int tile_i = 0; tile_i < row_tiles; ++tile_i) {
            multiply_row_tile(a, b, c, n, tile_i);
        }
    }
}
