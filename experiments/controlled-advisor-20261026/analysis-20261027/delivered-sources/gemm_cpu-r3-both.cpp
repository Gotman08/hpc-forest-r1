#include <cstddef>
#include <omp.h>

static inline void kernel_8x16(
    const float* a0, const float* a1, const float* a2, const float* a3,
    const float* a4, const float* a5, const float* a6, const float* a7,
    const float* b,
    float* c0, float* c1, float* c2, float* c3,
    float* c4, float* c5, float* c6, float* c7,
    std::size_t n)
{
    float acc[8][16] = {};
    std::size_t k = 0;
    for (; k + 1 < n; k += 2) {
        const float a00 = a0[k], a01 = a0[k + 1];
        const float a10 = a1[k], a11 = a1[k + 1];
        const float a20 = a2[k], a21 = a2[k + 1];
        const float a30 = a3[k], a31 = a3[k + 1];
        const float a40 = a4[k], a41 = a4[k + 1];
        const float a50 = a5[k], a51 = a5[k + 1];
        const float a60 = a6[k], a61 = a6[k + 1];
        const float a70 = a7[k], a71 = a7[k + 1];
        const float* bk0 = b + k * n;
        const float* bk1 = bk0 + n;

        #pragma omp simd
        for (int col = 0; col < 16; ++col) {
            const float b0 = bk0[col];
            const float b1 = bk1[col];
            acc[0][col] += a00 * b0;
            acc[0][col] += a01 * b1;
            acc[1][col] += a10 * b0;
            acc[1][col] += a11 * b1;
            acc[2][col] += a20 * b0;
            acc[2][col] += a21 * b1;
            acc[3][col] += a30 * b0;
            acc[3][col] += a31 * b1;
            acc[4][col] += a40 * b0;
            acc[4][col] += a41 * b1;
            acc[5][col] += a50 * b0;
            acc[5][col] += a51 * b1;
            acc[6][col] += a60 * b0;
            acc[6][col] += a61 * b1;
            acc[7][col] += a70 * b0;
            acc[7][col] += a71 * b1;
        }
    }

    if (k < n) {
        const float a0k = a0[k], a1k = a1[k], a2k = a2[k], a3k = a3[k];
        const float a4k = a4[k], a5k = a5[k], a6k = a6[k], a7k = a7[k];
        const float* bk = b + k * n;
        #pragma omp simd
        for (int col = 0; col < 16; ++col) {
            const float bv = bk[col];
            acc[0][col] += a0k * bv;
            acc[1][col] += a1k * bv;
            acc[2][col] += a2k * bv;
            acc[3][col] += a3k * bv;
            acc[4][col] += a4k * bv;
            acc[5][col] += a5k * bv;
            acc[6][col] += a6k * bv;
            acc[7][col] += a7k * bv;
        }
    }

    for (int col = 0; col < 16; ++col) {
        c0[col] = acc[0][col];
        c1[col] = acc[1][col];
        c2[col] = acc[2][col];
        c3[col] = acc[3][col];
        c4[col] = acc[4][col];
        c5[col] = acc[5][col];
        c6[col] = acc[6][col];
        c7[col] = acc[7][col];
    }
}

static inline void compute_row_group(const float* A, const float* B, float* C,
                                     int first_row, int n)
{
    const std::size_t N = static_cast<std::size_t>(n);
    const int remaining = n - first_row;
    const int rows = remaining < 8 ? remaining : 8;

    if (rows == 8) {
        int col = 0;
        for (; col <= n - 16; col += 16) {
            const std::size_t r0 = static_cast<std::size_t>(first_row) * N;
            const std::size_t r1 = static_cast<std::size_t>(first_row + 1) * N;
            const std::size_t r2 = static_cast<std::size_t>(first_row + 2) * N;
            const std::size_t r3 = static_cast<std::size_t>(first_row + 3) * N;
            const std::size_t r4 = static_cast<std::size_t>(first_row + 4) * N;
            const std::size_t r5 = static_cast<std::size_t>(first_row + 5) * N;
            const std::size_t r6 = static_cast<std::size_t>(first_row + 6) * N;
            const std::size_t r7 = static_cast<std::size_t>(first_row + 7) * N;
            const std::size_t c = static_cast<std::size_t>(col);
            kernel_8x16(A + r0, A + r1, A + r2, A + r3,
                        A + r4, A + r5, A + r6, A + r7,
                        B + c,
                        C + r0 + c, C + r1 + c, C + r2 + c, C + r3 + c,
                        C + r4 + c, C + r5 + c, C + r6 + c, C + r7 + c,
                        N);
        }

        for (; col < n; ++col) {
            float sums[8] = {};
            const std::size_t j = static_cast<std::size_t>(col);
            const std::size_t r0 = static_cast<std::size_t>(first_row) * N;
            const std::size_t r1 = static_cast<std::size_t>(first_row + 1) * N;
            const std::size_t r2 = static_cast<std::size_t>(first_row + 2) * N;
            const std::size_t r3 = static_cast<std::size_t>(first_row + 3) * N;
            const std::size_t r4 = static_cast<std::size_t>(first_row + 4) * N;
            const std::size_t r5 = static_cast<std::size_t>(first_row + 5) * N;
            const std::size_t r6 = static_cast<std::size_t>(first_row + 6) * N;
            const std::size_t r7 = static_cast<std::size_t>(first_row + 7) * N;
            for (std::size_t k = 0; k < N; ++k) {
                const float bv = B[k * N + j];
                sums[0] += A[r0 + k] * bv;
                sums[1] += A[r1 + k] * bv;
                sums[2] += A[r2 + k] * bv;
                sums[3] += A[r3 + k] * bv;
                sums[4] += A[r4 + k] * bv;
                sums[5] += A[r5 + k] * bv;
                sums[6] += A[r6 + k] * bv;
                sums[7] += A[r7 + k] * bv;
            }
            C[r0 + j] = sums[0];
            C[r1 + j] = sums[1];
            C[r2 + j] = sums[2];
            C[r3 + j] = sums[3];
            C[r4 + j] = sums[4];
            C[r5 + j] = sums[5];
            C[r6 + j] = sums[6];
            C[r7 + j] = sums[7];
        }
    } else {
        for (int row = first_row; row < first_row + rows; ++row) {
            const std::size_t row_offset = static_cast<std::size_t>(row) * N;
            for (int col = 0; col < n; ++col) {
                float sum = 0.0f;
                const std::size_t j = static_cast<std::size_t>(col);
                for (std::size_t k = 0; k < N; ++k) {
                    sum += A[row_offset + k] * B[k * N + j];
                }
                C[row_offset + j] = sum;
            }
        }
    }
}

extern "C" void run(const void* input1, const void* input2, void* output,
                    int n, int parameter, int threads)
{
    (void)parameter;
    if (n <= 0) {
        return;
    }

    const float* A = static_cast<const float*>(input1);
    const float* B = static_cast<const float*>(input2);
    float* C = static_cast<float*>(output);
    const int row_groups = n / 8 + (n % 8 != 0);

    if (threads <= 1 || row_groups <= 1 || omp_in_parallel()) {
        for (int group = 0; group < row_groups; ++group) {
            compute_row_group(A, B, C, group * 8, n);
        }
    } else {
        const int team = threads < row_groups ? threads : row_groups;
        #pragma omp parallel for schedule(static) num_threads(team)
        for (int group = 0; group < row_groups; ++group) {
            compute_row_group(A, B, C, group * 8, n);
        }
    }
}
