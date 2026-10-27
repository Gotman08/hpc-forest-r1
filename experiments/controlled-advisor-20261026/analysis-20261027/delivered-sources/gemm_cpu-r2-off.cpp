#include <algorithm>
#include <cstddef>
#include <omp.h>

static inline void microkernel_8x16(const float* A, const float* B, float* C,
                                    int n, int row, int col) {
    float acc[8][16] = {};
    const std::size_t stride = static_cast<std::size_t>(n);

    int k = 0;
    for (; k + 1 < n; k += 2) {
        const std::size_t arow = static_cast<std::size_t>(row) * stride +
                                 static_cast<std::size_t>(k);
        const float a00 = A[arow];
        const float a01 = A[arow + 1];
        const float a10 = A[arow + stride];
        const float a11 = A[arow + stride + 1];
        const float a20 = A[arow + 2 * stride];
        const float a21 = A[arow + 2 * stride + 1];
        const float a30 = A[arow + 3 * stride];
        const float a31 = A[arow + 3 * stride + 1];
        const float a40 = A[arow + 4 * stride];
        const float a41 = A[arow + 4 * stride + 1];
        const float a50 = A[arow + 5 * stride];
        const float a51 = A[arow + 5 * stride + 1];
        const float a60 = A[arow + 6 * stride];
        const float a61 = A[arow + 6 * stride + 1];
        const float a70 = A[arow + 7 * stride];
        const float a71 = A[arow + 7 * stride + 1];
        const std::size_t brow0 = static_cast<std::size_t>(k) * stride +
                                  static_cast<std::size_t>(col);
        const float* bp0 = B + brow0;
        const float* bp1 = B + brow0 + stride;

        #pragma omp simd
        for (int c = 0; c < 16; ++c) {
            const float b0 = bp0[c];
            const float b1 = bp1[c];
            acc[0][c] += a00 * b0;
            acc[0][c] += a01 * b1;
            acc[1][c] += a10 * b0;
            acc[1][c] += a11 * b1;
            acc[2][c] += a20 * b0;
            acc[2][c] += a21 * b1;
            acc[3][c] += a30 * b0;
            acc[3][c] += a31 * b1;
            acc[4][c] += a40 * b0;
            acc[4][c] += a41 * b1;
            acc[5][c] += a50 * b0;
            acc[5][c] += a51 * b1;
            acc[6][c] += a60 * b0;
            acc[6][c] += a61 * b1;
            acc[7][c] += a70 * b0;
            acc[7][c] += a71 * b1;
        }
    }

    if (k < n) {
        const std::size_t arow = static_cast<std::size_t>(row) * stride +
                                 static_cast<std::size_t>(k);
        const float a0 = A[arow];
        const float a1 = A[arow + stride];
        const float a2 = A[arow + 2 * stride];
        const float a3 = A[arow + 3 * stride];
        const float a4 = A[arow + 4 * stride];
        const float a5 = A[arow + 5 * stride];
        const float a6 = A[arow + 6 * stride];
        const float a7 = A[arow + 7 * stride];
        const float* bp = B + static_cast<std::size_t>(k) * stride +
                          static_cast<std::size_t>(col);

        #pragma omp simd
        for (int c = 0; c < 16; ++c) {
            const float b = bp[c];
            acc[0][c] += a0 * b;
            acc[1][c] += a1 * b;
            acc[2][c] += a2 * b;
            acc[3][c] += a3 * b;
            acc[4][c] += a4 * b;
            acc[5][c] += a5 * b;
            acc[6][c] += a6 * b;
            acc[7][c] += a7 * b;
        }
    }

    for (int r = 0; r < 8; ++r) {
        float* cp = C + static_cast<std::size_t>(row + r) * stride +
                    static_cast<std::size_t>(col);
        #pragma omp simd
        for (int c = 0; c < 16; ++c)
            cp[c] = acc[r][c];
    }
}

static inline void scalar_cell(const float* A, const float* B, float* C,
                               int n, int row, int col) {
    float sum = 0.0f;
    const float* ar = A + static_cast<std::size_t>(row) *
                           static_cast<std::size_t>(n);
    for (int k = 0; k < n; ++k)
        sum += ar[k] * B[static_cast<std::size_t>(k) *
                         static_cast<std::size_t>(n) +
                         static_cast<std::size_t>(col)];
    C[static_cast<std::size_t>(row) * static_cast<std::size_t>(n) +
      static_cast<std::size_t>(col)] = sum;
}

extern "C" void run(const void* input1, const void* input2, void* output,
                    int n, int parameter, int threads) {
    (void)parameter;
    const float* A = static_cast<const float*>(input1);
    const float* B = static_cast<const float*>(input2);
    float* C = static_cast<float*>(output);

    const int macro_rows = n / 64 + (n % 64 != 0);
    const int workers = std::max(1, std::min(threads, macro_rows));

    #pragma omp parallel for schedule(static) num_threads(workers)
    for (int iblock = 0; iblock < macro_rows; ++iblock) {
        const int ib = iblock * 64;
        const int iLimit = (n - ib < 64) ? n : ib + 64;
        const int iFull = ib + ((iLimit - ib) / 8) * 8;

        for (int jb = 0; jb < n;) {
            const int jLimit = (n - jb < 64) ? n : jb + 64;
            const int jFull = jb + ((jLimit - jb) / 16) * 16;

            for (int i = ib; i < iFull; i += 8)
                for (int j = jb; j < jFull; j += 16)
                    microkernel_8x16(A, B, C, n, i, j);

            for (int i = ib; i < iFull; ++i)
                for (int j = jFull; j < jLimit; ++j)
                    scalar_cell(A, B, C, n, i, j);

            for (int i = iFull; i < iLimit; ++i)
                for (int j = jb; j < jLimit; ++j)
                    scalar_cell(A, B, C, n, i, j);

            jb = jLimit;
        }
    }
}
