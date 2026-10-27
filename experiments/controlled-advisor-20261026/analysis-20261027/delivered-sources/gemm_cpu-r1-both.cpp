#include <cstddef>

static inline void microkernel_8x16(int n, int row, int col,
                                    const float* A, const float* B, float* C)
{
    const std::size_t stride = static_cast<std::size_t>(n);
    float acc[8][16] = {};

    const float* a0 = A + static_cast<std::size_t>(row + 0) * stride;
    const float* a1 = A + static_cast<std::size_t>(row + 1) * stride;
    const float* a2 = A + static_cast<std::size_t>(row + 2) * stride;
    const float* a3 = A + static_cast<std::size_t>(row + 3) * stride;
    const float* a4 = A + static_cast<std::size_t>(row + 4) * stride;
    const float* a5 = A + static_cast<std::size_t>(row + 5) * stride;
    const float* a6 = A + static_cast<std::size_t>(row + 6) * stride;
    const float* a7 = A + static_cast<std::size_t>(row + 7) * stride;

    for (int k = 0; k < n; ++k) {
        const float va0 = a0[k];
        const float va1 = a1[k];
        const float va2 = a2[k];
        const float va3 = a3[k];
        const float va4 = a4[k];
        const float va5 = a5[k];
        const float va6 = a6[k];
        const float va7 = a7[k];
        const float* brow = B + static_cast<std::size_t>(k) * stride + col;

        #pragma omp simd
        for (int c = 0; c < 16; ++c) {
            const float vb = brow[c];
            acc[0][c] += va0 * vb;
            acc[1][c] += va1 * vb;
            acc[2][c] += va2 * vb;
            acc[3][c] += va3 * vb;
            acc[4][c] += va4 * vb;
            acc[5][c] += va5 * vb;
            acc[6][c] += va6 * vb;
            acc[7][c] += va7 * vb;
        }
    }

    const std::size_t output_base = static_cast<std::size_t>(row) * stride + col;
    for (std::size_t i = 0; i < 8; ++i) {
        #pragma omp simd
        for (int c = 0; c < 16; ++c)
            C[output_base + i * stride + c] = acc[i][c];
    }
}

static inline void compute_scalar_columns(int n, int row, int first_col,
                                          int last_col, const float* A,
                                          const float* B, float* C)
{
    const std::size_t stride = static_cast<std::size_t>(n);
    const std::size_t row_offset = static_cast<std::size_t>(row) * stride;
    const float* arow = A + row_offset;

    for (int c = first_col; c < last_col; ++c) {
        float sum = 0.0f;
        for (int k = 0; k < n; ++k)
            sum += arow[k] * B[static_cast<std::size_t>(k) * stride + c];
        C[row_offset + c] = sum;
    }
}

extern "C" void run(const void* input1, const void* input2, void* output,
                    int n, int parameter, int threads)
{
    (void)parameter;

    const float* A = static_cast<const float*>(input1);
    const float* B = static_cast<const float*>(input2);
    float* C = static_cast<float*>(output);

    const int complete_cols = (n / 16) * 16;
    const int row_groups = n / 8 + (n % 8 != 0);
    const int workers = threads < 1 ? 1 : (threads > 4 ? 4 : threads);

    #pragma omp parallel for schedule(static) num_threads(workers)
    for (int group = 0; group < row_groups; ++group) {
        const int row = group * 8;
        if (n - row >= 8) {
            for (int col = 0; col < complete_cols; col += 16)
                microkernel_8x16(n, row, col, A, B, C);

            for (int r = row; r < row + 8; ++r)
                compute_scalar_columns(n, r, complete_cols, n, A, B, C);
        } else {
            for (int r = row; r < n; ++r)
                compute_scalar_columns(n, r, 0, n, A, B, C);
        }
    }
}
