#include <cstddef>

static inline void microkernel8x16(const float* A, const float* B, float* C,
                                   std::size_t N, std::size_t row0,
                                   std::size_t col0) {
    float acc[8][16] = {};

    for (std::size_t k = 0; k < N; ++k) {
        const std::size_t aidx = row0 * N + k;
        const float a0 = A[aidx];
        const float a1 = A[aidx + N];
        const float a2 = A[aidx + 2 * N];
        const float a3 = A[aidx + 3 * N];
        const float a4 = A[aidx + 4 * N];
        const float a5 = A[aidx + 5 * N];
        const float a6 = A[aidx + 6 * N];
        const float a7 = A[aidx + 7 * N];
        const float* brow = B + k * N + col0;

        #pragma omp simd
        for (std::size_t c = 0; c < 16; ++c) {
            const float b = brow[c];
            acc[0][c] += a0 * b;
            acc[1][c] += a1 * b;
            acc[2][c] += a2 * b;
            acc[3][c] += a3 * b;
            acc[4][c] += a4 * b;
            acc[5][c] += a5 * b;
            acc[6][c] += a6 * b;
            acc[7][c] += a7 * b;
        }
    }

    for (std::size_t r = 0; r < 8; ++r)
        for (std::size_t c = 0; c < 16; ++c)
            C[(row0 + r) * N + col0 + c] = acc[r][c];
}

static inline void scalar_output(const float* A, const float* B, float* C,
                                 std::size_t N, std::size_t row,
                                 std::size_t col) {
    float sum = 0.0f;
    for (std::size_t k = 0; k < N; ++k)
        sum += A[row * N + k] * B[k * N + col];
    C[row * N + col] = sum;
}

static inline void compute_tile(const float* A, const float* B, float* C,
                                std::size_t N, std::size_t row_block,
                                std::size_t col_block) {
    const std::size_t row0 = row_block * 8;
    const std::size_t col0 = col_block * 16;
    const std::size_t rows = (N - row0 < 8) ? N - row0 : 8;
    const std::size_t cols = (N - col0 < 16) ? N - col0 : 16;

    if (rows == 8 && cols == 16) {
        microkernel8x16(A, B, C, N, row0, col0);
    } else {
        for (std::size_t r = row0; r < row0 + rows; ++r)
            for (std::size_t c = col0; c < col0 + cols; ++c)
                scalar_output(A, B, C, N, r, c);
    }
}

static inline void compute_grouped_panel_tile(const float* A, const float* B,
                                              float* C, std::size_t N,
                                              std::size_t tile,
                                              std::size_t row_blocks,
                                              std::size_t col_blocks) {
    const std::size_t inner_col = tile % 4;
    const std::size_t row_block = (tile / 4) % row_blocks;
    const std::size_t panel_group = (tile / 4) / row_blocks;
    const std::size_t col_block = panel_group * 4 + inner_col;

    if (col_block < col_blocks)
        compute_tile(A, B, C, N, row_block, col_block);
}

extern "C" void run(const void* input1, const void* input2, void* output,
                    int n, int parameter, int threads) {
    (void)parameter;
    if (n <= 0)
        return;

    const float* A = static_cast<const float*>(input1);
    const float* B = static_cast<const float*>(input2);
    float* C = static_cast<float*>(output);
    const std::size_t N = static_cast<std::size_t>(n);
    const std::size_t row_blocks = (N + 7) / 8;
    const std::size_t col_blocks = (N + 15) / 16;
    const std::size_t tile_count = row_blocks * col_blocks;
    const std::size_t panel_groups = (col_blocks + 3) / 4;
    const std::size_t work_items = panel_groups * row_blocks * 4;

    int team_size = threads > 0 ? threads : 1;
    if (tile_count < static_cast<std::size_t>(team_size))
        team_size = static_cast<int>(tile_count);

    if (team_size > 1) {
        const long long work = static_cast<long long>(work_items);
        #pragma omp parallel for schedule(static) num_threads(team_size)
        for (long long tile = 0; tile < work; ++tile)
            compute_grouped_panel_tile(A, B, C, N,
                                       static_cast<std::size_t>(tile),
                                       row_blocks, col_blocks);
    } else {
        for (std::size_t tile = 0; tile < work_items; ++tile)
            compute_grouped_panel_tile(A, B, C, N, tile, row_blocks, col_blocks);
    }
}
