#include <cstddef>

static inline void multiply_tile_4x64(const float* a, const float* b, float* c,
                                      int n, int row, int col) {
    float acc[4][64] = {};
    const std::size_t nn = static_cast<std::size_t>(n);
    const std::size_t a0 = static_cast<std::size_t>(row) * nn;
    const std::size_t a1 = a0 + nn;
    const std::size_t a2 = a1 + nn;
    const std::size_t a3 = a2 + nn;

    for (int k = 0; k < n; ++k) {
        const float* bp = b + static_cast<std::size_t>(k) * nn + col;
        const float av0 = a[a0 + static_cast<std::size_t>(k)];
        const float av1 = a[a1 + static_cast<std::size_t>(k)];
        const float av2 = a[a2 + static_cast<std::size_t>(k)];
        const float av3 = a[a3 + static_cast<std::size_t>(k)];

        #pragma omp simd
        for (int j = 0; j < 64; ++j) {
            const float bv = bp[j];
            acc[0][j] += av0 * bv;
            acc[1][j] += av1 * bv;
            acc[2][j] += av2 * bv;
            acc[3][j] += av3 * bv;
        }
    }

    const std::size_t c0 = static_cast<std::size_t>(row) * nn + col;
    for (int j = 0; j < 64; ++j) {
        c[c0 + j] = acc[0][j];
        c[c0 + nn + j] = acc[1][j];
        c[c0 + 2 * nn + j] = acc[2][j];
        c[c0 + 3 * nn + j] = acc[3][j];
    }
}

static inline void multiply_row_group_4x64(const float* a, const float* b,
                                           float* c, int n, int row,
                                           int full_rows, int full_cols) {
    const std::size_t nn = static_cast<std::size_t>(n);

    if (row < full_rows) {
        for (int col = 0; col < full_cols; col += 64) {
            multiply_tile_4x64(a, b, c, n, row, col);
        }

        for (int col = full_cols; col < n; ++col) {
            for (int r = 0; r < 4; ++r) {
                const std::size_t ar = static_cast<std::size_t>(row + r) * nn;
                float sum = 0.0f;
                for (int k = 0; k < n; ++k) {
                    sum += a[ar + static_cast<std::size_t>(k)] *
                           b[static_cast<std::size_t>(k) * nn + col];
                }
                c[ar + static_cast<std::size_t>(col)] = sum;
            }
        }
        return;
    }

    for (int r = 0; r < n - row; ++r) {
        const std::size_t ar = static_cast<std::size_t>(row + r) * nn;
        for (int col = 0; col < n; ++col) {
            float sum = 0.0f;
            for (int k = 0; k < n; ++k) {
                sum += a[ar + static_cast<std::size_t>(k)] *
                       b[static_cast<std::size_t>(k) * nn + col];
            }
            c[ar + static_cast<std::size_t>(col)] = sum;
        }
    }
}

extern "C" void run(const void* input1, const void* input2, void* output,
                     int n, int parameter, int threads) {
    (void)parameter;
    if (n <= 0) return;

    const float* a = static_cast<const float*>(input1);
    const float* b = static_cast<const float*>(input2);
    float* c = static_cast<float*>(output);
    const int full_rows = n - n % 4;
    const int full_cols = n - n % 64;
    const int row_groups = n / 4 + (n % 4 != 0 ? 1 : 0);

    int worker_count = threads;
    if (worker_count > row_groups) worker_count = row_groups;

    if (worker_count <= 1) {
        for (int group = 0; group < row_groups; ++group) {
            multiply_row_group_4x64(a, b, c, n, group * 4,
                                    full_rows, full_cols);
        }
        return;
    }

    #pragma omp parallel for schedule(static) num_threads(worker_count)
    for (int group = 0; group < row_groups; ++group) {
        multiply_row_group_4x64(a, b, c, n, group * 4,
                                full_rows, full_cols);
    }
}
