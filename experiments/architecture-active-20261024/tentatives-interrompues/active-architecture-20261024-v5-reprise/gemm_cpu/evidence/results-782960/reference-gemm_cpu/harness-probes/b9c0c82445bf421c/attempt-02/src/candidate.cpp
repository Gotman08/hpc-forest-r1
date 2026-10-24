#include <cstddef>

static int min_int(int lhs, int rhs) {
    return lhs < rhs ? lhs : rhs;
}

static void blocked_gemm(const float* A, const float* B, float* C, int n, int threads) {
    if (n <= 0) return;

    const int BM = 32;
    const int BN = 64;
    const int BK = 64;
    const int MR = 4;
    const int NR = 8;
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

        for (int ii = row_begin; ii < row_end; ii += MR) {
            const int rows = min_int(MR, row_end - ii);
            for (int jj = col_begin; jj < col_end; jj += NR) {
                const int cols = min_int(NR, col_end - jj);
                const std::size_t cbase = static_cast<std::size_t>(ii) * stride + static_cast<std::size_t>(jj);

                for (int kb = 0; kb < n;) {
                    const int kend = kb + min_int(BK, n - kb);
                    if (rows == 4 && cols == 8) {
                        const std::size_t arow0 = static_cast<std::size_t>(ii) * stride;
                        const std::size_t arow1 = static_cast<std::size_t>(ii + 1) * stride;
                        const std::size_t arow2 = static_cast<std::size_t>(ii + 2) * stride;
                        const std::size_t arow3 = static_cast<std::size_t>(ii + 3) * stride;

                        float c00 = kb == 0 ? 0.0f : C[cbase];
                        float c01 = kb == 0 ? 0.0f : C[cbase + 1];
                        float c02 = kb == 0 ? 0.0f : C[cbase + 2];
                        float c03 = kb == 0 ? 0.0f : C[cbase + 3];
                        float c04 = kb == 0 ? 0.0f : C[cbase + 4];
                        float c05 = kb == 0 ? 0.0f : C[cbase + 5];
                        float c06 = kb == 0 ? 0.0f : C[cbase + 6];
                        float c07 = kb == 0 ? 0.0f : C[cbase + 7];
                        float c10 = kb == 0 ? 0.0f : C[cbase + stride];
                        float c11 = kb == 0 ? 0.0f : C[cbase + stride + 1];
                        float c12 = kb == 0 ? 0.0f : C[cbase + stride + 2];
                        float c13 = kb == 0 ? 0.0f : C[cbase + stride + 3];
                        float c14 = kb == 0 ? 0.0f : C[cbase + stride + 4];
                        float c15 = kb == 0 ? 0.0f : C[cbase + stride + 5];
                        float c16 = kb == 0 ? 0.0f : C[cbase + stride + 6];
                        float c17 = kb == 0 ? 0.0f : C[cbase + stride + 7];
                        float c20 = kb == 0 ? 0.0f : C[cbase + 2 * stride];
                        float c21 = kb == 0 ? 0.0f : C[cbase + 2 * stride + 1];
                        float c22 = kb == 0 ? 0.0f : C[cbase + 2 * stride + 2];
                        float c23 = kb == 0 ? 0.0f : C[cbase + 2 * stride + 3];
                        float c24 = kb == 0 ? 0.0f : C[cbase + 2 * stride + 4];
                        float c25 = kb == 0 ? 0.0f : C[cbase + 2 * stride + 5];
                        float c26 = kb == 0 ? 0.0f : C[cbase + 2 * stride + 6];
                        float c27 = kb == 0 ? 0.0f : C[cbase + 2 * stride + 7];
                        float c30 = kb == 0 ? 0.0f : C[cbase + 3 * stride];
                        float c31 = kb == 0 ? 0.0f : C[cbase + 3 * stride + 1];
                        float c32 = kb == 0 ? 0.0f : C[cbase + 3 * stride + 2];
                        float c33 = kb == 0 ? 0.0f : C[cbase + 3 * stride + 3];
                        float c34 = kb == 0 ? 0.0f : C[cbase + 3 * stride + 4];
                        float c35 = kb == 0 ? 0.0f : C[cbase + 3 * stride + 5];
                        float c36 = kb == 0 ? 0.0f : C[cbase + 3 * stride + 6];
                        float c37 = kb == 0 ? 0.0f : C[cbase + 3 * stride + 7];

                        for (int k = kb; k < kend; ++k) {
                            const std::size_t kk = static_cast<std::size_t>(k);
                            const std::size_t bbase = kk * stride + static_cast<std::size_t>(jj);
                            const float b0 = B[bbase];
                            const float b1 = B[bbase + 1];
                            const float b2 = B[bbase + 2];
                            const float b3 = B[bbase + 3];
                            const float b4 = B[bbase + 4];
                            const float b5 = B[bbase + 5];
                            const float b6 = B[bbase + 6];
                            const float b7 = B[bbase + 7];
                            const float a0 = A[arow0 + kk];
                            const float a1 = A[arow1 + kk];
                            const float a2 = A[arow2 + kk];
                            const float a3 = A[arow3 + kk];
                            c00 += a0 * b0; c01 += a0 * b1; c02 += a0 * b2; c03 += a0 * b3;
                            c04 += a0 * b4; c05 += a0 * b5; c06 += a0 * b6; c07 += a0 * b7;
                            c10 += a1 * b0; c11 += a1 * b1; c12 += a1 * b2; c13 += a1 * b3;
                            c14 += a1 * b4; c15 += a1 * b5; c16 += a1 * b6; c17 += a1 * b7;
                            c20 += a2 * b0; c21 += a2 * b1; c22 += a2 * b2; c23 += a2 * b3;
                            c24 += a2 * b4; c25 += a2 * b5; c26 += a2 * b6; c27 += a2 * b7;
                            c30 += a3 * b0; c31 += a3 * b1; c32 += a3 * b2; c33 += a3 * b3;
                            c34 += a3 * b4; c35 += a3 * b5; c36 += a3 * b6; c37 += a3 * b7;
                        }

                        C[cbase] = c00; C[cbase + 1] = c01; C[cbase + 2] = c02; C[cbase + 3] = c03;
                        C[cbase + 4] = c04; C[cbase + 5] = c05; C[cbase + 6] = c06; C[cbase + 7] = c07;
                        C[cbase + stride] = c10; C[cbase + stride + 1] = c11;
                        C[cbase + stride + 2] = c12; C[cbase + stride + 3] = c13;
                        C[cbase + stride + 4] = c14; C[cbase + stride + 5] = c15;
                        C[cbase + stride + 6] = c16; C[cbase + stride + 7] = c17;
                        C[cbase + 2 * stride] = c20; C[cbase + 2 * stride + 1] = c21;
                        C[cbase + 2 * stride + 2] = c22; C[cbase + 2 * stride + 3] = c23;
                        C[cbase + 2 * stride + 4] = c24; C[cbase + 2 * stride + 5] = c25;
                        C[cbase + 2 * stride + 6] = c26; C[cbase + 2 * stride + 7] = c27;
                        C[cbase + 3 * stride] = c30; C[cbase + 3 * stride + 1] = c31;
                        C[cbase + 3 * stride + 2] = c32; C[cbase + 3 * stride + 3] = c33;
                        C[cbase + 3 * stride + 4] = c34; C[cbase + 3 * stride + 5] = c35;
                        C[cbase + 3 * stride + 6] = c36; C[cbase + 3 * stride + 7] = c37;
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
