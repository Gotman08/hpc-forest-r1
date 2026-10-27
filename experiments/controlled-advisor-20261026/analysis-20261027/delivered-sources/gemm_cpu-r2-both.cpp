#include <algorithm>
#include <cstddef>

extern "C" void run(const void* input1, const void* input2, void* output,
                    int n, int parameter, int threads)
{
    (void)parameter;
    if (n <= 0) return;

    const float* A = static_cast<const float*>(input1);
    const float* B = static_cast<const float*>(input2);
    float* C = static_cast<float*>(output);
    const std::size_t size = static_cast<std::size_t>(n);
    constexpr int row_block = 16;
    constexpr int col_block = 16;
    const int row_groups = n / row_block + (n % row_block != 0);
    const int full_cols = (n / col_block) * col_block;

    int worker_count = threads > 0 ? threads : 1;
    if (worker_count > row_groups) worker_count = row_groups;

    // Assign disjoint row tiles statically, with workers bounded by the budget
    // and the number of available tiles.
#pragma omp parallel for schedule(static) num_threads(worker_count) if(worker_count > 1)
    for (int block = 0; block < row_groups; ++block) {
        const int r = block * row_block;

        if (n - r >= row_block) {
            const std::size_t row0 = static_cast<std::size_t>(r) * size;

            for (int c0 = 0; c0 < full_cols; c0 += col_block) {
                float acc[16][16] = {};
                for (int k = 0; k < n; ++k) {
                    const std::size_t kk = static_cast<std::size_t>(k);
                    const float a0 = A[row0 + kk];
                    const float a1 = A[row0 + size + kk];
                    const float a2 = A[row0 + 2 * size + kk];
                    const float a3 = A[row0 + 3 * size + kk];
                    const float a4 = A[row0 + 4 * size + kk];
                    const float a5 = A[row0 + 5 * size + kk];
                    const float a6 = A[row0 + 6 * size + kk];
                    const float a7 = A[row0 + 7 * size + kk];
                    const float a8 = A[row0 + 8 * size + kk];
                    const float a9 = A[row0 + 9 * size + kk];
                    const float a10 = A[row0 + 10 * size + kk];
                    const float a11 = A[row0 + 11 * size + kk];
                    const float a12 = A[row0 + 12 * size + kk];
                    const float a13 = A[row0 + 13 * size + kk];
                    const float a14 = A[row0 + 14 * size + kk];
                    const float a15 = A[row0 + 15 * size + kk];
                    const float* bp = B + kk * size + static_cast<std::size_t>(c0);

#pragma omp simd
                    for (int c = 0; c < col_block; ++c) {
                        const float b = bp[c];
                        acc[0][c] += a0 * b;
                        acc[1][c] += a1 * b;
                        acc[2][c] += a2 * b;
                        acc[3][c] += a3 * b;
                        acc[4][c] += a4 * b;
                        acc[5][c] += a5 * b;
                        acc[6][c] += a6 * b;
                        acc[7][c] += a7 * b;
                        acc[8][c] += a8 * b;
                        acc[9][c] += a9 * b;
                        acc[10][c] += a10 * b;
                        acc[11][c] += a11 * b;
                        acc[12][c] += a12 * b;
                        acc[13][c] += a13 * b;
                        acc[14][c] += a14 * b;
                        acc[15][c] += a15 * b;
                    }
                }

                for (int rr = 0; rr < row_block; ++rr) {
                    float* cp = C + row0 + static_cast<std::size_t>(rr) * size + c0;
                    for (int c = 0; c < col_block; ++c)
                        cp[c] = acc[rr][c];
                }
            }

            // Scalar column tail; each output accumulates in increasing k order.
            for (int c = full_cols; c < n; ++c) {
                const std::size_t col = static_cast<std::size_t>(c);
                for (int rr = 0; rr < row_block; ++rr) {
                    const std::size_t row = row0 + static_cast<std::size_t>(rr) * size;
                    float sum = 0.0f;
                    for (int k = 0; k < n; ++k) {
                        const std::size_t kk = static_cast<std::size_t>(k);
                        sum += A[row + kk] * B[kk * size + col];
                    }
                    C[row + col] = sum;
                }
            }
        } else {
            // Handle the final one to fifteen rows with 1x16 SIMD chunks.
            for (int rr = r; rr < n; ++rr) {
                const std::size_t row = static_cast<std::size_t>(rr) * size;
                for (int c0 = 0; c0 < n; c0 += col_block) {
                    const int cols = std::min(col_block, n - c0);
                    float acc[16] = {};
                    for (int k = 0; k < n; ++k) {
                        const float a = A[row + static_cast<std::size_t>(k)];
                        const float* bp = B + static_cast<std::size_t>(k) * size + c0;
#pragma omp simd
                        for (int c = 0; c < cols; ++c)
                            acc[c] += a * bp[c];
                    }
                    float* cp = C + row + c0;
                    for (int c = 0; c < cols; ++c)
                        cp[c] = acc[c];
                }
            }
        }
    }
}
