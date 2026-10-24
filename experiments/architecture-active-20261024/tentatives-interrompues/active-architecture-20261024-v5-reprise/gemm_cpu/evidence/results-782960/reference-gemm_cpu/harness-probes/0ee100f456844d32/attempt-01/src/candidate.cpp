#include <algorithm>
#include <cstddef>

namespace {

const int TILE_M = 64;
const int TILE_N = 64;
const int TILE_K = 64;
const int MICRO = 4;

inline void multiply_edge(const float* a, const float* b, float* c,
                          int n, int row, int column) {
    const std::size_t stride = static_cast<std::size_t>(n);
    const std::size_t row_offset = static_cast<std::size_t>(row) * stride;
    float sum = 0.0f;
    for (int k = 0; k < n; ++k) {
        sum += a[row_offset + static_cast<std::size_t>(k)] *
               b[static_cast<std::size_t>(k) * stride +
                 static_cast<std::size_t>(column)];
    }
    c[row_offset + static_cast<std::size_t>(column)] = sum;
}

}  // namespace

extern "C" void run(const void* input1, const void* input2, void* output,
                    int n, int parameter, int threads) {
    (void)parameter;
    (void)threads;
    if (n <= 0) {
        return;
    }

    const float* a = static_cast<const float*>(input1);
    const float* b = static_cast<const float*>(input2);
    float* c = static_cast<float*>(output);
    const std::size_t stride = static_cast<std::size_t>(n);

    const int tile_rows = n / TILE_M + (n % TILE_M != 0);
    const int tile_columns = n / TILE_N + (n % TILE_N != 0);
    const long long tile_count =
        static_cast<long long>(tile_rows) * tile_columns;

#ifdef _OPENMP
    const int requested_workers = threads > 0 ? threads : 1;
    const int worker_count = static_cast<int>(
        std::min<long long>(tile_count, requested_workers));
#pragma omp parallel for schedule(static) num_threads(worker_count) if(worker_count > 1)
#endif
    for (long long tile = 0; tile < tile_count; ++tile) {
        const int tile_i = static_cast<int>(tile / tile_columns) * TILE_M;
        const int tile_j = static_cast<int>(tile % tile_columns) * TILE_N;
        const int row_end = tile_i + std::min(TILE_M, n - tile_i);
        const int column_end = tile_j + std::min(TILE_N, n - tile_j);
        const int full_row_end =
            tile_i + ((row_end - tile_i) / MICRO) * MICRO;
        const int full_column_end =
            tile_j + ((column_end - tile_j) / MICRO) * MICRO;

        for (int i = tile_i; i < full_row_end; i += MICRO) {
            const std::size_t a_row0 = static_cast<std::size_t>(i) * stride;
            const std::size_t a_row1 = a_row0 + stride;
            const std::size_t a_row2 = a_row1 + stride;
            const std::size_t a_row3 = a_row2 + stride;
            const std::size_t c_row0 = a_row0;
            const std::size_t c_row1 = a_row1;
            const std::size_t c_row2 = a_row2;
            const std::size_t c_row3 = a_row3;

            for (int j = tile_j; j < full_column_end; j += MICRO) {
                float c00 = 0.0f, c01 = 0.0f, c02 = 0.0f, c03 = 0.0f;
                float c10 = 0.0f, c11 = 0.0f, c12 = 0.0f, c13 = 0.0f;
                float c20 = 0.0f, c21 = 0.0f, c22 = 0.0f, c23 = 0.0f;
                float c30 = 0.0f, c31 = 0.0f, c32 = 0.0f, c33 = 0.0f;

                for (int k_begin = 0; k_begin < n; k_begin += TILE_K) {
                    const int k_end = std::min(k_begin + TILE_K, n);
                    if (k_begin != 0) {
                        const std::size_t c_index = c_row0 + static_cast<std::size_t>(j);
                        c00 = c[c_index];
                        c01 = c[c_index + 1];
                        c02 = c[c_index + 2];
                        c03 = c[c_index + 3];
                        c10 = c[c_index + stride];
                        c11 = c[c_index + stride + 1];
                        c12 = c[c_index + stride + 2];
                        c13 = c[c_index + stride + 3];
                        c20 = c[c_index + 2 * stride];
                        c21 = c[c_index + 2 * stride + 1];
                        c22 = c[c_index + 2 * stride + 2];
                        c23 = c[c_index + 2 * stride + 3];
                        c30 = c[c_index + 3 * stride];
                        c31 = c[c_index + 3 * stride + 1];
                        c32 = c[c_index + 3 * stride + 2];
                        c33 = c[c_index + 3 * stride + 3];
                    }

                    for (int k = k_begin; k < k_end; ++k) {
                        const float a0 = a[a_row0 + static_cast<std::size_t>(k)];
                        const float a1 = a[a_row1 + static_cast<std::size_t>(k)];
                        const float a2 = a[a_row2 + static_cast<std::size_t>(k)];
                        const float a3 = a[a_row3 + static_cast<std::size_t>(k)];
                        const std::size_t b_index =
                            static_cast<std::size_t>(k) * stride +
                            static_cast<std::size_t>(j);
                        const float b0 = b[b_index];
                        const float b1 = b[b_index + 1];
                        const float b2 = b[b_index + 2];
                        const float b3 = b[b_index + 3];

                        c00 += a0 * b0; c01 += a0 * b1;
                        c02 += a0 * b2; c03 += a0 * b3;
                        c10 += a1 * b0; c11 += a1 * b1;
                        c12 += a1 * b2; c13 += a1 * b3;
                        c20 += a2 * b0; c21 += a2 * b1;
                        c22 += a2 * b2; c23 += a2 * b3;
                        c30 += a3 * b0; c31 += a3 * b1;
                        c32 += a3 * b2; c33 += a3 * b3;
                    }
                }

                const std::size_t c_index = c_row0 + static_cast<std::size_t>(j);
                c[c_index] = c00; c[c_index + 1] = c01;
                c[c_index + 2] = c02; c[c_index + 3] = c03;
                c[c_index + stride] = c10; c[c_index + stride + 1] = c11;
                c[c_index + stride + 2] = c12; c[c_index + stride + 3] = c13;
                c[c_index + 2 * stride] = c20; c[c_index + 2 * stride + 1] = c21;
                c[c_index + 2 * stride + 2] = c22; c[c_index + 2 * stride + 3] = c23;
                c[c_index + 3 * stride] = c30; c[c_index + 3 * stride + 1] = c31;
                c[c_index + 3 * stride + 2] = c32; c[c_index + 3 * stride + 3] = c33;
            }
        }

        for (int i = full_row_end; i < row_end; ++i) {
            for (int j = tile_j; j < column_end; ++j) {
                multiply_edge(a, b, c, n, i, j);
            }
        }
        for (int i = tile_i; i < full_row_end; ++i) {
            for (int j = full_column_end; j < column_end; ++j) {
                multiply_edge(a, b, c, n, i, j);
            }
        }
    }
}
