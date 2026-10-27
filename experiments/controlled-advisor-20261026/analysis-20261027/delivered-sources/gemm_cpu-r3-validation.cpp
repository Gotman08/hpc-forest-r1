#include <algorithm>
#include <cstddef>

static inline void compute_tile(const float* A, const float* B, float* C,
                                std::size_t dim, std::size_t r0,
                                std::size_t c0) {
    const std::size_t rows = std::min<std::size_t>(4, dim - r0);
    const std::size_t cols = std::min<std::size_t>(16, dim - c0);

    if (rows == 4 && cols == 16) {
        float acc[4][16] = {};
        std::size_t k = 0;
        for (; k + 1 < dim; k += 2) {
            const float* b0 = B + k * dim + c0;
            const float* b1 = B + (k + 1) * dim + c0;
            const float a00 = A[(r0 + 0) * dim + k];
            const float a01 = A[(r0 + 0) * dim + k + 1];
            const float a10 = A[(r0 + 1) * dim + k];
            const float a11 = A[(r0 + 1) * dim + k + 1];
            const float a20 = A[(r0 + 2) * dim + k];
            const float a21 = A[(r0 + 2) * dim + k + 1];
            const float a30 = A[(r0 + 3) * dim + k];
            const float a31 = A[(r0 + 3) * dim + k + 1];

            #pragma omp simd
            for (int j = 0; j < 16; ++j) {
                const float v0 = b0[j];
                const float v1 = b1[j];
                acc[0][j] += a00 * v0;
                acc[0][j] += a01 * v1;
                acc[1][j] += a10 * v0;
                acc[1][j] += a11 * v1;
                acc[2][j] += a20 * v0;
                acc[2][j] += a21 * v1;
                acc[3][j] += a30 * v0;
                acc[3][j] += a31 * v1;
            }
        }

        if (k < dim) {
            const float* b = B + k * dim + c0;
            const float a0 = A[(r0 + 0) * dim + k];
            const float a1 = A[(r0 + 1) * dim + k];
            const float a2 = A[(r0 + 2) * dim + k];
            const float a3 = A[(r0 + 3) * dim + k];
            #pragma omp simd
            for (int j = 0; j < 16; ++j) {
                const float v = b[j];
                acc[0][j] += a0 * v;
                acc[1][j] += a1 * v;
                acc[2][j] += a2 * v;
                acc[3][j] += a3 * v;
            }
        }

        #pragma omp simd
        for (int j = 0; j < 16; ++j) {
            C[(r0 + 0) * dim + c0 + j] = acc[0][j];
            C[(r0 + 1) * dim + c0 + j] = acc[1][j];
            C[(r0 + 2) * dim + c0 + j] = acc[2][j];
            C[(r0 + 3) * dim + c0 + j] = acc[3][j];
        }
    } else {
        for (std::size_t i = 0; i < rows; ++i) {
            for (std::size_t j = 0; j < cols; ++j) {
                float sum = 0.0f;
                for (std::size_t k = 0; k < dim; ++k) {
                    sum += A[(r0 + i) * dim + k] *
                           B[k * dim + c0 + j];
                }
                C[(r0 + i) * dim + c0 + j] = sum;
            }
        }
    }
}

extern "C" void run(const void* input1, const void* input2, void* output,
                    int n, int parameter, int threads) {
    (void)parameter;
    if (n <= 0) return;

    const std::size_t dim = static_cast<std::size_t>(n);
    const float* A = static_cast<const float*>(input1);
    const float* B = static_cast<const float*>(input2);
    float* C = static_cast<float*>(output);

    const std::size_t row_tiles = dim / 4 + (dim % 4 != 0);
    const std::size_t col_tiles = dim / 16 + (dim % 16 != 0);
    const std::size_t tile_count = row_tiles * col_tiles;

    if (threads <= 1 || n <= 1 || tile_count <= 1) {
        for (std::size_t row_tile = 0; row_tile < row_tiles; ++row_tile) {
            const std::size_t r0 = row_tile * 4;
            for (std::size_t col_tile = 0; col_tile < col_tiles; ++col_tile) {
                compute_tile(A, B, C, dim, r0, col_tile * 16);
            }
        }
    } else {
        const int worker_count = tile_count < static_cast<std::size_t>(threads)
                                     ? static_cast<int>(tile_count)
                                     : threads;
        #pragma omp parallel for schedule(static) num_threads(worker_count)
        for (std::size_t tile = 0; tile < tile_count; ++tile) {
            const std::size_t row_tile = tile / col_tiles;
            const std::size_t col_tile = tile % col_tiles;
            compute_tile(A, B, C, dim, row_tile * 4, col_tile * 16);
        }
    }
}
