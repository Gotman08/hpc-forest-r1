#include <algorithm>
#include <cstddef>
#include <omp.h>

static inline void compute_row(const float* A, const float* B, float* C,
                               int n, int i) {
    const std::size_t offset = static_cast<std::size_t>(i) * n;
    const float* arow = A + offset;
    float* crow = C + offset;
    const float* brow = B;

    const float a0 = arow[0];
#pragma omp simd
    for (int j = 0; j < n; ++j)
        crow[j] = a0 * brow[j];

    for (int k = 1; k < n; ++k) {
        const float aik = arow[k];
        brow = B + static_cast<std::size_t>(k) * n;
#pragma omp simd
        for (int j = 0; j < n; ++j)
            crow[j] += aik * brow[j];
    }
}

static inline void compute_row_pair(const float* A, const float* B, float* C,
                                    int n, int i) {
    const std::size_t offset0 = static_cast<std::size_t>(i) * n;
    const std::size_t offset1 = static_cast<std::size_t>(i + 1) * n;
    const float* arow0 = A + offset0;
    const float* arow1 = A + offset1;
    float* crow0 = C + offset0;
    float* crow1 = C + offset1;
    const float* brow = B;

    const float a00 = arow0[0];
    const float a10 = arow1[0];
#pragma omp simd
    for (int j = 0; j < n; ++j) {
        const float b = brow[j];
        crow0[j] = a00 * b;
        crow1[j] = a10 * b;
    }

    for (int k = 1; k < n; ++k) {
        const float a0 = arow0[k];
        const float a1 = arow1[k];
        brow = B + static_cast<std::size_t>(k) * n;
#pragma omp simd
        for (int j = 0; j < n; ++j) {
            const float b = brow[j];
            crow0[j] += a0 * b;
            crow1[j] += a1 * b;
        }
    }
}

static inline void update_tile_4x8(float accum[4][8], const float* A,
                                   const float* B, int n, int r, int c,
                                   int k) {
    const std::size_t nn = static_cast<std::size_t>(n);
    const std::size_t row_a = static_cast<std::size_t>(r) * nn +
                              static_cast<std::size_t>(k);
    const std::size_t row_b = static_cast<std::size_t>(k) * nn +
                              static_cast<std::size_t>(c);
    for (int i = 0; i < 4; ++i) {
        const float aik = A[row_a + static_cast<std::size_t>(i) * nn];
        for (int j = 0; j < 8; ++j)
            accum[i][j] += aik * B[row_b + static_cast<std::size_t>(j)];
    }
}

static inline void multiply_tile_4x8(const float* A, const float* B, float* C,
                                     int n, int r, int c) {
    float accum[4][8] = {};
    int k = 0;
    for (; k < n - 1; k += 2) {
        update_tile_4x8(accum, A, B, n, r, c, k);
        update_tile_4x8(accum, A, B, n, r, c, k + 1);
    }
    if (k < n)
        update_tile_4x8(accum, A, B, n, r, c, k);

    const std::size_t nn = static_cast<std::size_t>(n);
    for (int i = 0; i < 4; ++i) {
        const std::size_t row_c = static_cast<std::size_t>(r + i) * nn +
                                  static_cast<std::size_t>(c);
        for (int j = 0; j < 8; ++j)
            C[row_c + static_cast<std::size_t>(j)] = accum[i][j];
    }
}

static inline float dot_product(const float* A, const float* B, int n,
                                int r, int c) {
    const std::size_t nn = static_cast<std::size_t>(n);
    const std::size_t row_a = static_cast<std::size_t>(r) * nn;
    float sum = 0.0f;
    for (int k = 0; k < n; ++k)
        sum += A[row_a + static_cast<std::size_t>(k)] *
               B[static_cast<std::size_t>(k) * nn + static_cast<std::size_t>(c)];
    return sum;
}

static inline void compute_row_panel(const float* A, const float* B, float* C,
                                     int n, std::size_t row0, int col0,
                                     int col_end) {
    const std::size_t nn = static_cast<std::size_t>(n);
    if (row0 + 4 > nn) {
        for (std::size_t r = row0; r < nn; ++r) {
            for (int c = col0; c < col_end; ++c)
                C[r * nn + static_cast<std::size_t>(c)] =
                    dot_product(A, B, n, static_cast<int>(r), c);
        }
        return;
    }

    int c = col0;
    while (col_end - c >= 8) {
        multiply_tile_4x8(A, B, C, n, static_cast<int>(row0), c);
        c += 8;
    }
    for (; c < col_end; ++c) {
        for (int i = 0; i < 4; ++i) {
            const int r = static_cast<int>(row0) + i;
            C[static_cast<std::size_t>(r) * nn + static_cast<std::size_t>(c)] =
                dot_product(A, B, n, r, c);
        }
    }
}

extern "C" void run(const void* input1, const void* input2, void* output,
                    int n, int parameter, int threads) {
    (void)parameter;
    if (n <= 0)
        return;

    const float* A = static_cast<const float*>(input1);
    const float* B = static_cast<const float*>(input2);
    float* C = static_cast<float*>(output);

    // Keep the measured row-pair path for serial and small workloads.
    if (threads <= 1 || n < 64) {
        const int row_blocks = n / 2 + n % 2;
        for (int block = 0; block < row_blocks; ++block) {
            const int i = block * 2;
            if (i + 1 < n)
                compute_row_pair(A, B, C, n, i);
            else
                compute_row(A, B, C, n, i);
        }
        return;
    }

    constexpr int panel_columns = 128;
    const int row_blocks = n / 4 + (n % 4 != 0);
    const int panel_count = 1 + (n - 1) / panel_columns;
    const long long work_items = static_cast<long long>(row_blocks) * panel_count;
    const int worker_count = static_cast<int>(
        std::min<long long>(static_cast<long long>(threads), work_items));

    // Each work item owns one four-row block and one column panel.
#pragma omp parallel for schedule(static) num_threads(worker_count)
    for (long long item = 0; item < work_items; ++item) {
        const int panel = static_cast<int>(item / row_blocks);
        const int row_block = static_cast<int>(item % row_blocks);
        const int col0 = panel * panel_columns;
        const int col_end = col0 + std::min(panel_columns, n - col0);
        const std::size_t row0 = static_cast<std::size_t>(row_block) * 4;
        compute_row_panel(A, B, C, n, row0, col0, col_end);
    }
}
