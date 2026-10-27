#include <algorithm>
#include <cstddef>
#include <cstdint>
#include <omp.h>

namespace {
constexpr int ROW_TILE = 8;
constexpr int COL_TILE = 16;

inline void compute_tile(const float* A, const float* B, float* C, int n,
                         std::int64_t tile, std::int64_t col_tiles) {
    const int row0 = static_cast<int>((tile / col_tiles) * ROW_TILE);
    const int col0 = static_cast<int>((tile % col_tiles) * COL_TILE);
    const int rows = std::min(ROW_TILE, n - row0);
    const int cols = std::min(COL_TILE, n - col0);
    const std::size_t N = static_cast<std::size_t>(n);

    if (rows == ROW_TILE && cols == COL_TILE) {
        float acc[ROW_TILE][COL_TILE] = {};
        const std::size_t row0_offset = static_cast<std::size_t>(row0) * N;
        const std::size_t row1 = row0_offset + N;
        const std::size_t row2 = row1 + N;
        const std::size_t row3 = row2 + N;
        const std::size_t row4 = row3 + N;
        const std::size_t row5 = row4 + N;
        const std::size_t row6 = row5 + N;
        const std::size_t row7 = row6 + N;
        const std::size_t col_offset = static_cast<std::size_t>(col0);

        int k = 0;
        for (; k + 1 < n; k += 2) {
            const std::size_t kp = static_cast<std::size_t>(k);
            const std::size_t bp = kp * N + col_offset;
            const float a00 = A[row0_offset + kp];
            const float a01 = A[row0_offset + kp + 1];
            const float a10 = A[row1 + kp];
            const float a11 = A[row1 + kp + 1];
            const float a20 = A[row2 + kp];
            const float a21 = A[row2 + kp + 1];
            const float a30 = A[row3 + kp];
            const float a31 = A[row3 + kp + 1];
            const float a40 = A[row4 + kp];
            const float a41 = A[row4 + kp + 1];
            const float a50 = A[row5 + kp];
            const float a51 = A[row5 + kp + 1];
            const float a60 = A[row6 + kp];
            const float a61 = A[row6 + kp + 1];
            const float a70 = A[row7 + kp];
            const float a71 = A[row7 + kp + 1];

            #pragma omp simd
            for (int jj = 0; jj < COL_TILE; ++jj) {
                const float b0 = B[bp + static_cast<std::size_t>(jj)];
                const float b1 = B[bp + N + static_cast<std::size_t>(jj)];
                acc[0][jj] += a00 * b0;
                acc[0][jj] += a01 * b1;
                acc[1][jj] += a10 * b0;
                acc[1][jj] += a11 * b1;
                acc[2][jj] += a20 * b0;
                acc[2][jj] += a21 * b1;
                acc[3][jj] += a30 * b0;
                acc[3][jj] += a31 * b1;
                acc[4][jj] += a40 * b0;
                acc[4][jj] += a41 * b1;
                acc[5][jj] += a50 * b0;
                acc[5][jj] += a51 * b1;
                acc[6][jj] += a60 * b0;
                acc[6][jj] += a61 * b1;
                acc[7][jj] += a70 * b0;
                acc[7][jj] += a71 * b1;
            }
        }

        if (k < n) {
            const std::size_t kp = static_cast<std::size_t>(k);
            const std::size_t bp = kp * N + col_offset;
            const float a0 = A[row0_offset + kp];
            const float a1 = A[row1 + kp];
            const float a2 = A[row2 + kp];
            const float a3 = A[row3 + kp];
            const float a4 = A[row4 + kp];
            const float a5 = A[row5 + kp];
            const float a6 = A[row6 + kp];
            const float a7 = A[row7 + kp];

            #pragma omp simd
            for (int jj = 0; jj < COL_TILE; ++jj) {
                const float b = B[bp + static_cast<std::size_t>(jj)];
                acc[0][jj] += a0 * b;
                acc[1][jj] += a1 * b;
                acc[2][jj] += a2 * b;
                acc[3][jj] += a3 * b;
                acc[4][jj] += a4 * b;
                acc[5][jj] += a5 * b;
                acc[6][jj] += a6 * b;
                acc[7][jj] += a7 * b;
            }
        }

        for (int r = 0; r < ROW_TILE; ++r) {
            const std::size_t out = row0_offset + static_cast<std::size_t>(r) * N +
                                    col_offset;
            #pragma omp simd
            for (int jj = 0; jj < COL_TILE; ++jj)
                C[out + static_cast<std::size_t>(jj)] = acc[r][jj];
        }
    } else {
        for (int r = 0; r < rows; ++r) {
            const std::size_t arow = static_cast<std::size_t>(row0 + r) * N;
            const std::size_t crow = arow + static_cast<std::size_t>(col0);
            for (int c = 0; c < cols; ++c) {
                float sum = 0.0f;
                const std::size_t bcol = static_cast<std::size_t>(col0 + c);
                for (int k = 0; k < n; ++k)
                    sum += A[arow + static_cast<std::size_t>(k)] *
                           B[static_cast<std::size_t>(k) * N + bcol];
                C[crow + static_cast<std::size_t>(c)] = sum;
            }
        }
    }
}

inline void compute_tile_serial(const float* A, const float* B, float* C, int n,
                                std::int64_t tile, std::int64_t col_tiles) {
    const int row0 = static_cast<int>((tile / col_tiles) * ROW_TILE);
    const int col0 = static_cast<int>((tile % col_tiles) * COL_TILE);
    const int rows = std::min(ROW_TILE, n - row0);
    const int cols = std::min(COL_TILE, n - col0);
    const std::size_t N = static_cast<std::size_t>(n);

    // Keep the existing edge path; only full tiles use the serial K-unroll test.
    if (rows != ROW_TILE || cols != COL_TILE) {
        compute_tile(A, B, C, n, tile, col_tiles);
        return;
    }

    float acc[ROW_TILE][COL_TILE] = {};
    const std::size_t row0_offset = static_cast<std::size_t>(row0) * N;
    const std::size_t row1 = row0_offset + N;
    const std::size_t row2 = row1 + N;
    const std::size_t row3 = row2 + N;
    const std::size_t row4 = row3 + N;
    const std::size_t row5 = row4 + N;
    const std::size_t row6 = row5 + N;
    const std::size_t row7 = row6 + N;
    const std::size_t col_offset = static_cast<std::size_t>(col0);

    int k = 0;
    for (; k + 3 < n; k += 4) {
        const std::size_t kp = static_cast<std::size_t>(k);
        const std::size_t bp = kp * N + col_offset;
        const float a00 = A[row0_offset + kp];
        const float a01 = A[row0_offset + kp + 1];
        const float a02 = A[row0_offset + kp + 2];
        const float a03 = A[row0_offset + kp + 3];
        const float a10 = A[row1 + kp];
        const float a11 = A[row1 + kp + 1];
        const float a12 = A[row1 + kp + 2];
        const float a13 = A[row1 + kp + 3];
        const float a20 = A[row2 + kp];
        const float a21 = A[row2 + kp + 1];
        const float a22 = A[row2 + kp + 2];
        const float a23 = A[row2 + kp + 3];
        const float a30 = A[row3 + kp];
        const float a31 = A[row3 + kp + 1];
        const float a32 = A[row3 + kp + 2];
        const float a33 = A[row3 + kp + 3];
        const float a40 = A[row4 + kp];
        const float a41 = A[row4 + kp + 1];
        const float a42 = A[row4 + kp + 2];
        const float a43 = A[row4 + kp + 3];
        const float a50 = A[row5 + kp];
        const float a51 = A[row5 + kp + 1];
        const float a52 = A[row5 + kp + 2];
        const float a53 = A[row5 + kp + 3];
        const float a60 = A[row6 + kp];
        const float a61 = A[row6 + kp + 1];
        const float a62 = A[row6 + kp + 2];
        const float a63 = A[row6 + kp + 3];
        const float a70 = A[row7 + kp];
        const float a71 = A[row7 + kp + 1];
        const float a72 = A[row7 + kp + 2];
        const float a73 = A[row7 + kp + 3];

        #pragma omp simd
        for (int jj = 0; jj < COL_TILE; ++jj) {
            const std::size_t j = static_cast<std::size_t>(jj);
            const float b0 = B[bp + j];
            const float b1 = B[bp + N + j];
            const float b2 = B[bp + 2 * N + j];
            const float b3 = B[bp + 3 * N + j];
            acc[0][jj] += a00 * b0;
            acc[0][jj] += a01 * b1;
            acc[0][jj] += a02 * b2;
            acc[0][jj] += a03 * b3;
            acc[1][jj] += a10 * b0;
            acc[1][jj] += a11 * b1;
            acc[1][jj] += a12 * b2;
            acc[1][jj] += a13 * b3;
            acc[2][jj] += a20 * b0;
            acc[2][jj] += a21 * b1;
            acc[2][jj] += a22 * b2;
            acc[2][jj] += a23 * b3;
            acc[3][jj] += a30 * b0;
            acc[3][jj] += a31 * b1;
            acc[3][jj] += a32 * b2;
            acc[3][jj] += a33 * b3;
            acc[4][jj] += a40 * b0;
            acc[4][jj] += a41 * b1;
            acc[4][jj] += a42 * b2;
            acc[4][jj] += a43 * b3;
            acc[5][jj] += a50 * b0;
            acc[5][jj] += a51 * b1;
            acc[5][jj] += a52 * b2;
            acc[5][jj] += a53 * b3;
            acc[6][jj] += a60 * b0;
            acc[6][jj] += a61 * b1;
            acc[6][jj] += a62 * b2;
            acc[6][jj] += a63 * b3;
            acc[7][jj] += a70 * b0;
            acc[7][jj] += a71 * b1;
            acc[7][jj] += a72 * b2;
            acc[7][jj] += a73 * b3;
        }
    }

    for (; k < n; ++k) {
        const std::size_t kp = static_cast<std::size_t>(k);
        const std::size_t bp = kp * N + col_offset;
        const float a0 = A[row0_offset + kp];
        const float a1 = A[row1 + kp];
        const float a2 = A[row2 + kp];
        const float a3 = A[row3 + kp];
        const float a4 = A[row4 + kp];
        const float a5 = A[row5 + kp];
        const float a6 = A[row6 + kp];
        const float a7 = A[row7 + kp];

        #pragma omp simd
        for (int jj = 0; jj < COL_TILE; ++jj) {
            const float b = B[bp + static_cast<std::size_t>(jj)];
            acc[0][jj] += a0 * b;
            acc[1][jj] += a1 * b;
            acc[2][jj] += a2 * b;
            acc[3][jj] += a3 * b;
            acc[4][jj] += a4 * b;
            acc[5][jj] += a5 * b;
            acc[6][jj] += a6 * b;
            acc[7][jj] += a7 * b;
        }
    }

    for (int r = 0; r < ROW_TILE; ++r) {
        const std::size_t out = row0_offset + static_cast<std::size_t>(r) * N +
                                col_offset;
        #pragma omp simd
        for (int jj = 0; jj < COL_TILE; ++jj)
            C[out + static_cast<std::size_t>(jj)] = acc[r][jj];
    }
}
}

extern "C" void run(const void* input1, const void* input2, void* output,
                    int n, int parameter, int threads) {
    (void)parameter;
    if (n <= 0) return;

    const float* A = static_cast<const float*>(input1);
    const float* B = static_cast<const float*>(input2);
    float* C = static_cast<float*>(output);
    const std::int64_t row_tiles =
        (static_cast<std::int64_t>(n) + ROW_TILE - 1) / ROW_TILE;
    const std::int64_t col_tiles =
        (static_cast<std::int64_t>(n) + COL_TILE - 1) / COL_TILE;
    const std::int64_t tile_count = row_tiles * col_tiles;

    if (threads == 1 && !omp_in_parallel()) {
        for (std::int64_t tile = 0; tile < tile_count; ++tile)
            compute_tile_serial(A, B, C, n, tile, col_tiles);
    } else if (threads > 1 && !omp_in_parallel()) {
        int team = threads;
        if (tile_count < static_cast<std::int64_t>(team))
            team = static_cast<int>(tile_count);
        #pragma omp parallel for schedule(static) num_threads(team)
        for (std::int64_t tile = 0; tile < tile_count; ++tile)
            compute_tile(A, B, C, n, tile, col_tiles);
    } else {
        for (std::int64_t tile = 0; tile < tile_count; ++tile)
            compute_tile(A, B, C, n, tile, col_tiles);
    }
}
