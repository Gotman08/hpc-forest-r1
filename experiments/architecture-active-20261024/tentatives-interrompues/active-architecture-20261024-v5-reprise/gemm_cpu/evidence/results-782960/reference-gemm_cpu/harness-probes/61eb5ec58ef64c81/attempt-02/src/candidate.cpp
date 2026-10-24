#include <cstddef>

static int min_int(int lhs, int rhs) {
    return lhs < rhs ? lhs : rhs;
}

static void blocked_gemm(const float* A, const float* B, float* C, int n, int threads) {
    if (n <= 0) return;

    const int BM = 32;
    const int BN = 64;
    const int BK = 64;
    const int tile_rows = 1 + (n - 1) / BM;
    const int tile_cols = 1 + (n - 1) / BN;
    const int tile_count = tile_rows * tile_cols;
    const std::size_t stride = static_cast<std::size_t>(n);

    int worker_count = threads > 0 ? threads : 1;
    if (worker_count > tile_count) worker_count = tile_count;
    if (worker_count < 1) worker_count = 1;

#if defined(_OPENMP)
#pragma omp parallel for schedule(static) num_threads(worker_count) if(worker_count > 1)
#endif
    for (int tile = 0; tile < tile_count; ++tile) {
        const int tile_row = tile / tile_cols;
        const int tile_col = tile % tile_cols;
        const int row_begin = tile_row * BM;
        const int col_begin = tile_col * BN;
        const int row_end = row_begin + min_int(BM, n - row_begin);
        const int col_end = col_begin + min_int(BN, n - col_begin);

        for (int ii = row_begin; ii < row_end; ii += 4) {
            const int rows = min_int(4, row_end - ii);
            for (int jj = col_begin; jj < col_end; jj += 4) {
                const int cols = min_int(4, col_end - jj);
                const std::size_t cbase = static_cast<std::size_t>(ii) * stride + static_cast<std::size_t>(jj);

                for (int kb = 0; kb < n;) {
                    const int kend = kb + min_int(BK, n - kb);
                    if (rows == 4 && cols == 4) {
                        const std::size_t arow0 = static_cast<std::size_t>(ii) * stride;
                        const std::size_t arow1 = static_cast<std::size_t>(ii + 1) * stride;
                        const std::size_t arow2 = static_cast<std::size_t>(ii + 2) * stride;
                        const std::size_t arow3 = static_cast<std::size_t>(ii + 3) * stride;
                        float c00 = kb == 0 ? 0.0f : C[cbase];
                        float c01 = kb == 0 ? 0.0f : C[cbase + 1];
                        float c02 = kb == 0 ? 0.0f : C[cbase + 2];
                        float c03 = kb == 0 ? 0.0f : C[cbase + 3];
                        float c10 = kb == 0 ? 0.0f : C[cbase + stride];
                        float c11 = kb == 0 ? 0.0f : C[cbase + stride + 1];
                        float c12 = kb == 0 ? 0.0f : C[cbase + stride + 2];
                        float c13 = kb == 0 ? 0.0f : C[cbase + stride + 3];
                        float c20 = kb == 0 ? 0.0f : C[cbase + 2 * stride];
                        float c21 = kb == 0 ? 0.0f : C[cbase + 2 * stride + 1];
                        float c22 = kb == 0 ? 0.0f : C[cbase + 2 * stride + 2];
                        float c23 = kb == 0 ? 0.0f : C[cbase + 2 * stride + 3];
                        float c30 = kb == 0 ? 0.0f : C[cbase + 3 * stride];
                        float c31 = kb == 0 ? 0.0f : C[cbase + 3 * stride + 1];
                        float c32 = kb == 0 ? 0.0f : C[cbase + 3 * stride + 2];
                        float c33 = kb == 0 ? 0.0f : C[cbase + 3 * stride + 3];

                        for (int k = kb; k < kend; ++k) {
                            const std::size_t kk = static_cast<std::size_t>(k);
                            const std::size_t bbase = kk * stride + static_cast<std::size_t>(jj);
                            const float b0 = B[bbase];
                            const float b1 = B[bbase + 1];
                            const float b2 = B[bbase + 2];
                            const float b3 = B[bbase + 3];
                            const float a0 = A[arow0 + kk];
                            const float a1 = A[arow1 + kk];
                            const float a2 = A[arow2 + kk];
                            const float a3 = A[arow3 + kk];
                            c00 += a0 * b0; c01 += a0 * b1; c02 += a0 * b2; c03 += a0 * b3;
                            c10 += a1 * b0; c11 += a1 * b1; c12 += a1 * b2; c13 += a1 * b3;
                            c20 += a2 * b0; c21 += a2 * b1; c22 += a2 * b2; c23 += a2 * b3;
                            c30 += a3 * b0; c31 += a3 * b1; c32 += a3 * b2; c33 += a3 * b3;
                        }

                        C[cbase] = c00; C[cbase + 1] = c01; C[cbase + 2] = c02; C[cbase + 3] = c03;
                        C[cbase + stride] = c10; C[cbase + stride + 1] = c11; C[cbase + stride + 2] = c12; C[cbase + stride + 3] = c13;
                        C[cbase + 2 * stride] = c20; C[cbase + 2 * stride + 1] = c21; C[cbase + 2 * stride + 2] = c22; C[cbase + 2 * stride + 3] = c23;
                        C[cbase + 3 * stride] = c30; C[cbase + 3 * stride + 1] = c31; C[cbase + 3 * stride + 2] = c32; C[cbase + 3 * stride + 3] = c33;
                    } else {
                        for (int r = 0; r < rows; ++r) {
                            const std::size_t arow = static_cast<std::size_t>(ii + r) * stride;
                            for (int c = 0; c < cols; ++c) {
                                const std::size_t out_index = arow + static_cast<std::size_t>(jj + c);
                                float sum = kb == 0 ? 0.0f : C[out_index];
                                for (int k = kb; k < kend; ++k) {
                                    const std::size_t kk = static_cast<std::size_t>(k);
                                    sum += A[arow + kk] * B[kk * stride + static_cast<std::size_t>(jj + c)];
                                }
                                C[out_index] = sum;
                            }
                        }
                    }
                    kb = kend;
                }
            }
        }
    }
}

extern "C" void run(const void* input1, const void* input2, void* output, int n, int parameter, int threads) {
    (void)parameter;
    blocked_gemm(static_cast<const float*>(input1), static_cast<const float*>(input2), static_cast<float*>(output), n, threads);
}
