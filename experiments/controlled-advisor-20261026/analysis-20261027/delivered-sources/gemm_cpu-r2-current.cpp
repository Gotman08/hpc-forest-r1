#include <cstddef>

extern "C" void run(const void* input1, const void* input2, void* output,
                    int n, int parameter, int threads) {
    (void)parameter;
    if (n <= 0) return;

    const float* A = static_cast<const float*>(input1);
    const float* B = static_cast<const float*>(input2);
    float* C = static_cast<float*>(output);
    const std::size_t nn = static_cast<std::size_t>(n);
    constexpr int MR = 4;
    constexpr int NC = 32;
    const int col_full = n - n % NC;
    const int row_groups = 1 + (n - 1) / MR;

    // Each group owns up to four complete output rows.
    const auto process_group = [&](int group) {
        const int rb = group * MR;
        const int row_count = n - rb < MR ? n - rb : MR;

        if (row_count == MR) {
            for (int cb = 0; cb < col_full; cb += NC) {
                float acc[MR][NC] = {};
                const std::size_t a0row = static_cast<std::size_t>(rb) * nn;
                const std::size_t a1row = a0row + nn;
                const std::size_t a2row = a1row + nn;
                const std::size_t a3row = a2row + nn;

                int k = 0;
                for (; k <= n - 4; k += 4) {
                    const std::size_t kk = static_cast<std::size_t>(k);
                    const std::size_t brow0 = kk * nn +
                                              static_cast<std::size_t>(cb);
                    const std::size_t brow1 = brow0 + nn;
                    const std::size_t brow2 = brow1 + nn;
                    const std::size_t brow3 = brow2 + nn;

                    const float a00 = A[a0row + kk];
                    const float a10 = A[a1row + kk];
                    const float a20 = A[a2row + kk];
                    const float a30 = A[a3row + kk];
                    const float a01 = A[a0row + kk + 1];
                    const float a11 = A[a1row + kk + 1];
                    const float a21 = A[a2row + kk + 1];
                    const float a31 = A[a3row + kk + 1];
                    const float a02 = A[a0row + kk + 2];
                    const float a12 = A[a1row + kk + 2];
                    const float a22 = A[a2row + kk + 2];
                    const float a32 = A[a3row + kk + 2];
                    const float a03 = A[a0row + kk + 3];
                    const float a13 = A[a1row + kk + 3];
                    const float a23 = A[a2row + kk + 3];
                    const float a33 = A[a3row + kk + 3];

                    #pragma omp simd
                    for (int j = 0; j < NC; ++j) {
                        const std::size_t jj = static_cast<std::size_t>(j);
                        const float b0 = B[brow0 + jj];
                        acc[0][j] += a00 * b0;
                        acc[1][j] += a10 * b0;
                        acc[2][j] += a20 * b0;
                        acc[3][j] += a30 * b0;

                        const float b1 = B[brow1 + jj];
                        acc[0][j] += a01 * b1;
                        acc[1][j] += a11 * b1;
                        acc[2][j] += a21 * b1;
                        acc[3][j] += a31 * b1;

                        const float b2 = B[brow2 + jj];
                        acc[0][j] += a02 * b2;
                        acc[1][j] += a12 * b2;
                        acc[2][j] += a22 * b2;
                        acc[3][j] += a32 * b2;

                        const float b3 = B[brow3 + jj];
                        acc[0][j] += a03 * b3;
                        acc[1][j] += a13 * b3;
                        acc[2][j] += a23 * b3;
                        acc[3][j] += a33 * b3;
                    }
                }

                // Preserve the original K order for the remaining elements.
                for (; k < n; ++k) {
                    const float a0 = A[a0row + static_cast<std::size_t>(k)];
                    const float a1 = A[a1row + static_cast<std::size_t>(k)];
                    const float a2 = A[a2row + static_cast<std::size_t>(k)];
                    const float a3 = A[a3row + static_cast<std::size_t>(k)];
                    const std::size_t brow = static_cast<std::size_t>(k) * nn +
                                             static_cast<std::size_t>(cb);

                    #pragma omp simd
                    for (int j = 0; j < NC; ++j) {
                        const float b = B[brow + static_cast<std::size_t>(j)];
                        acc[0][j] += a0 * b;
                        acc[1][j] += a1 * b;
                        acc[2][j] += a2 * b;
                        acc[3][j] += a3 * b;
                    }
                }

                for (int i = 0; i < MR; ++i) {
                    const std::size_t crow =
                        static_cast<std::size_t>(rb + i) * nn +
                        static_cast<std::size_t>(cb);
                    for (int j = 0; j < NC; ++j)
                        C[crow + static_cast<std::size_t>(j)] = acc[i][j];
                }
            }

            // Compute any right-edge columns for this complete row group.
            for (int i = 0; i < MR; ++i) {
                const std::size_t arow = static_cast<std::size_t>(rb + i) * nn;
                for (int c = col_full; c < n; ++c) {
                    float sum = 0.0f;
                    for (int k = 0; k < n; ++k)
                        sum += A[arow + static_cast<std::size_t>(k)] *
                               B[static_cast<std::size_t>(k) * nn +
                                 static_cast<std::size_t>(c)];
                    C[arow + static_cast<std::size_t>(c)] = sum;
                }
            }
        } else {
            // Scalar bottom-edge path for any incomplete row group.
            for (int i = 0; i < row_count; ++i) {
                const std::size_t row = static_cast<std::size_t>(rb + i) * nn;
                for (int c = 0; c < n; ++c) {
                    float sum = 0.0f;
                    for (int k = 0; k < n; ++k)
                        sum += A[row + static_cast<std::size_t>(k)] *
                               B[static_cast<std::size_t>(k) * nn +
                                 static_cast<std::size_t>(c)];
                    C[row + static_cast<std::size_t>(c)] = sum;
                }
            }
        }
    };

    // Use no more than the requested positive budget or available row groups.
    int team_size = threads > 0 ? threads : 1;
    if (team_size > row_groups) team_size = row_groups;
    if (team_size > 1) {
        #pragma omp parallel for schedule(static) num_threads(team_size)
        for (int group = 0; group < row_groups; ++group)
            process_group(group);
    } else {
        for (int group = 0; group < row_groups; ++group)
            process_group(group);
    }
}
