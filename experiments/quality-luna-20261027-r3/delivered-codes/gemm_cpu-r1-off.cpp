#include <algorithm>
#include <cstddef>
#include <omp.h>

namespace {
constexpr std::size_t row_block = 8;
constexpr int column_block = 16;

inline void initialize_8x16(float (&acc)[8][16], const float* a,
                            std::size_t dim, std::size_t row0,
                            const float* b_row) {
    const std::size_t base = row0 * dim;
    const float a0 = a[base + 0 * dim];
    const float a1 = a[base + 1 * dim];
    const float a2 = a[base + 2 * dim];
    const float a3 = a[base + 3 * dim];
    const float a4 = a[base + 4 * dim];
    const float a5 = a[base + 5 * dim];
    const float a6 = a[base + 6 * dim];
    const float a7 = a[base + 7 * dim];

#pragma omp simd
    for (int j = 0; j < column_block; ++j) {
        const float value = b_row[j];
        acc[0][j] = a0 * value;
        acc[1][j] = a1 * value;
        acc[2][j] = a2 * value;
        acc[3][j] = a3 * value;
        acc[4][j] = a4 * value;
        acc[5][j] = a5 * value;
        acc[6][j] = a6 * value;
        acc[7][j] = a7 * value;
    }
}

inline void update_8x16(float (&acc)[8][16], const float* a,
                        std::size_t dim, std::size_t row0, std::size_t k,
                        const float* b_row) {
    const std::size_t base = row0 * dim + k;
    const float a0 = a[base + 0 * dim];
    const float a1 = a[base + 1 * dim];
    const float a2 = a[base + 2 * dim];
    const float a3 = a[base + 3 * dim];
    const float a4 = a[base + 4 * dim];
    const float a5 = a[base + 5 * dim];
    const float a6 = a[base + 6 * dim];
    const float a7 = a[base + 7 * dim];

#pragma omp simd
    for (int j = 0; j < column_block; ++j) {
        const float value = b_row[j];
        acc[0][j] += a0 * value;
        acc[1][j] += a1 * value;
        acc[2][j] += a2 * value;
        acc[3][j] += a3 * value;
        acc[4][j] += a4 * value;
        acc[5][j] += a5 * value;
        acc[6][j] += a6 * value;
        acc[7][j] += a7 * value;
    }
}

inline float dot_product(const float* a_row, const float* b,
                         std::size_t dim, std::size_t col) {
    float sum = a_row[0] * b[col];
    for (std::size_t k = 1; k < dim; ++k) {
        sum += a_row[k] * b[k * dim + col];
    }
    return sum;
}

void compute_row_block(std::size_t block, const float* a, const float* b,
                       float* c, std::size_t dim) {
    const std::size_t row0 = block * row_block;
    const std::size_t rows = std::min(row_block, dim - row0);
    const std::size_t full_columns = (dim / column_block) * column_block;

    if (rows == row_block) {
        for (std::size_t col0 = 0; col0 < full_columns;
             col0 += column_block) {
            float acc[8][16];
            initialize_8x16(acc, a, dim, row0, b + col0);

            std::size_t k = 1;
            for (; dim - k >= 4; k += 4) {
                update_8x16(acc, a, dim, row0, k + 0,
                            b + (k + 0) * dim + col0);
                update_8x16(acc, a, dim, row0, k + 1,
                            b + (k + 1) * dim + col0);
                update_8x16(acc, a, dim, row0, k + 2,
                            b + (k + 2) * dim + col0);
                update_8x16(acc, a, dim, row0, k + 3,
                            b + (k + 3) * dim + col0);
            }
            for (; k < dim; ++k) {
                update_8x16(acc, a, dim, row0, k, b + k * dim + col0);
            }

            for (std::size_t r = 0; r < row_block; ++r) {
                float* c_row = c + (row0 + r) * dim + col0;
                const float* acc_row = acc[r];
#pragma omp simd
                for (int j = 0; j < column_block; ++j) {
                    c_row[j] = acc_row[j];
                }
            }
        }

        for (std::size_t col = full_columns; col < dim; ++col) {
            for (std::size_t r = 0; r < row_block; ++r) {
                const std::size_t row = row0 + r;
                c[row * dim + col] = dot_product(a + row * dim, b, dim, col);
            }
        }
    } else {
        for (std::size_t r = 0; r < rows; ++r) {
            const std::size_t row = row0 + r;
            for (std::size_t col = 0; col < dim; ++col) {
                c[row * dim + col] = dot_product(a + row * dim, b, dim, col);
            }
        }
    }
}
}

extern "C" void run(const void* input1, const void* input2, void* output,
                    int n, int parameter, int threads) {
    (void)parameter;
    if (n <= 0) return;

    const std::size_t dim = static_cast<std::size_t>(n);
    const std::size_t block_count = dim / row_block + (dim % row_block != 0);
    const int requested = threads > 0 ? threads : 1;
    const int team = omp_in_parallel()
                         ? 1
                         : (requested < static_cast<int>(block_count)
                                ? requested
                                : static_cast<int>(block_count));
    const float* a = static_cast<const float*>(input1);
    const float* b = static_cast<const float*>(input2);
    float* c = static_cast<float*>(output);

#pragma omp parallel num_threads(team)
    {
        const std::size_t worker = static_cast<std::size_t>(omp_get_thread_num());
        const std::size_t workers = static_cast<std::size_t>(omp_get_num_threads());
        const std::size_t quotient = block_count / workers;
        const std::size_t remainder = block_count % workers;
        const std::size_t first = worker * quotient + std::min(worker, remainder);
        const std::size_t last = first + quotient + (worker < remainder ? 1 : 0);

        for (std::size_t block = first; block < last; ++block) {
            compute_row_block(block, a, b, c, dim);
        }
    }
}
