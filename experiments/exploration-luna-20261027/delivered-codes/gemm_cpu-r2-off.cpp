#include <cstddef>

namespace {
constexpr int kRowTile = 4;
constexpr int kColTile = 16;

void multiply_edge_tile(const float* a, const float* b, float* c, int n,
                        int row0, int col0, int rows, int cols) {
    const std::size_t stride = static_cast<std::size_t>(n);
    float accum[kRowTile][kColTile] = {};

    int k = 0;
    for (; k < n - 1; k += 2) {
        const float* b_row0 =
            b + static_cast<std::size_t>(k) * stride +
            static_cast<std::size_t>(col0);
        const float* b_row1 =
            b + static_cast<std::size_t>(k + 1) * stride +
            static_cast<std::size_t>(col0);

        for (int row = 0; row < rows; ++row) {
            const std::size_t a_row =
                static_cast<std::size_t>(row0 + row) * stride;
            const float a_value0 = a[a_row + static_cast<std::size_t>(k)];
            const float a_value1 = a[a_row + static_cast<std::size_t>(k + 1)];
            float* accum_row = accum[row];

#pragma omp simd
            for (int col = 0; col < cols; ++col) {
                accum_row[col] += a_value0 * b_row0[col];
                accum_row[col] += a_value1 * b_row1[col];
            }
        }
    }

    if (k < n) {
        const float* b_row =
            b + static_cast<std::size_t>(k) * stride +
            static_cast<std::size_t>(col0);

        for (int row = 0; row < rows; ++row) {
            const std::size_t a_index =
                static_cast<std::size_t>(row0 + row) * stride +
                static_cast<std::size_t>(k);
            const float a_value = a[a_index];
            float* accum_row = accum[row];

#pragma omp simd
            for (int col = 0; col < cols; ++col)
                accum_row[col] += a_value * b_row[col];
        }
    }

    for (int row = 0; row < rows; ++row) {
        float* c_row =
            c + static_cast<std::size_t>(row0 + row) * stride +
            static_cast<std::size_t>(col0);
        const float* accum_row = accum[row];

#pragma omp simd
        for (int col = 0; col < cols; ++col)
            c_row[col] = accum_row[col];
    }
}

void multiply(const float* a, const float* b, float* c, int n, int threads) {
    const std::size_t stride = static_cast<std::size_t>(n);
    const int full_rows = n - n % kRowTile;
    const int full_cols = n - n % kColTile;
    const int worker_count = threads > 1 ? threads : 1;

#pragma omp parallel for schedule(static) num_threads(worker_count) if(worker_count > 1)
    for (int col0 = 0; col0 < full_cols; col0 += kColTile) {
        for (int row0 = 0; row0 < full_rows; row0 += kRowTile) {
            float accum[kRowTile][kColTile] = {};

            int k = 0;
            for (; k < n - 1; k += 2) {
                const float* b_row0 =
                    b + static_cast<std::size_t>(k) * stride +
                    static_cast<std::size_t>(col0);
                const float* b_row1 =
                    b + static_cast<std::size_t>(k + 1) * stride +
                    static_cast<std::size_t>(col0);

                for (int row = 0; row < kRowTile; ++row) {
                    const std::size_t a_row =
                        static_cast<std::size_t>(row0 + row) * stride;
                    const float a_value0 =
                        a[a_row + static_cast<std::size_t>(k)];
                    const float a_value1 =
                        a[a_row + static_cast<std::size_t>(k + 1)];
                    float* accum_row = accum[row];

#pragma omp simd
                    for (int col = 0; col < kColTile; ++col) {
                        accum_row[col] += a_value0 * b_row0[col];
                        accum_row[col] += a_value1 * b_row1[col];
                    }
                }
            }

            if (k < n) {
                const float* b_row =
                    b + static_cast<std::size_t>(k) * stride +
                    static_cast<std::size_t>(col0);

                for (int row = 0; row < kRowTile; ++row) {
                    const std::size_t a_index =
                        static_cast<std::size_t>(row0 + row) * stride +
                        static_cast<std::size_t>(k);
                    const float a_value = a[a_index];
                    float* accum_row = accum[row];

#pragma omp simd
                    for (int col = 0; col < kColTile; ++col)
                        accum_row[col] += a_value * b_row[col];
                }
            }

            for (int row = 0; row < kRowTile; ++row) {
                float* c_row =
                    c + static_cast<std::size_t>(row0 + row) * stride +
                    static_cast<std::size_t>(col0);
                const float* accum_row = accum[row];

#pragma omp simd
                for (int col = 0; col < kColTile; ++col)
                    c_row[col] = accum_row[col];
            }
        }
    }

    if (full_cols < n) {
        for (int row0 = 0; row0 < full_rows; row0 += kRowTile)
            multiply_edge_tile(a, b, c, n, row0, full_cols, kRowTile,
                               n - full_cols);
    }

    if (full_rows < n) {
        const int rows = n - full_rows;
        for (int col0 = 0; col0 < n;) {
            int cols = n - col0;
            if (cols > kColTile)
                cols = kColTile;
            multiply_edge_tile(a, b, c, n, full_rows, col0, rows, cols);
            col0 += cols;
        }
    }
}
}  // namespace

extern "C" void run(const void* input1, const void* input2, void* output,
                    int n, int parameter, int threads) {
    (void)parameter;
    if (n <= 0)
        return;

    multiply(static_cast<const float*>(input1),
             static_cast<const float*>(input2),
             static_cast<float*>(output), n, threads);
}
