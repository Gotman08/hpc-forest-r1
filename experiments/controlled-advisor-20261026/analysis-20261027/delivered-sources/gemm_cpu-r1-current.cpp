#include <cstddef>
#include <omp.h>

namespace {
constexpr std::size_t MR = 4;
constexpr std::size_t NR = 64;
constexpr int ROW_GROUP = 8;

template <std::size_t WIDTH>
inline void compute_tile(const float* A, const float* B, float* C,
                         int n, std::size_t nn, std::size_t r0,
                         int rows, std::size_t c0)
{
    const std::size_t cols = WIDTH == 0 ? nn - c0 : WIDTH;
    float acc[MR][NR] = {};

    if (rows == static_cast<int>(MR)) {
        int k = 0;
        for (; k + 3 < n; k += 4) {
            const std::size_t kk = static_cast<std::size_t>(k);
            const float a00 = A[r0 * nn + kk + 0];
            const float a01 = A[r0 * nn + kk + 1];
            const float a02 = A[r0 * nn + kk + 2];
            const float a03 = A[r0 * nn + kk + 3];
            const float a10 = A[(r0 + 1) * nn + kk + 0];
            const float a11 = A[(r0 + 1) * nn + kk + 1];
            const float a12 = A[(r0 + 1) * nn + kk + 2];
            const float a13 = A[(r0 + 1) * nn + kk + 3];
            const float a20 = A[(r0 + 2) * nn + kk + 0];
            const float a21 = A[(r0 + 2) * nn + kk + 1];
            const float a22 = A[(r0 + 2) * nn + kk + 2];
            const float a23 = A[(r0 + 2) * nn + kk + 3];
            const float a30 = A[(r0 + 3) * nn + kk + 0];
            const float a31 = A[(r0 + 3) * nn + kk + 1];
            const float a32 = A[(r0 + 3) * nn + kk + 2];
            const float a33 = A[(r0 + 3) * nn + kk + 3];

            const float* b0 = B + kk * nn + c0;
            const float* b1 = b0 + nn;
            const float* b2 = b1 + nn;
            const float* b3 = b2 + nn;

            #pragma omp simd
            for (std::size_t j = 0; j < cols; ++j) {
                const float x0 = b0[j];
                const float x1 = b1[j];
                const float x2 = b2[j];
                const float x3 = b3[j];
                acc[0][j] += a00 * x0;
                acc[0][j] += a01 * x1;
                acc[0][j] += a02 * x2;
                acc[0][j] += a03 * x3;
                acc[1][j] += a10 * x0;
                acc[1][j] += a11 * x1;
                acc[1][j] += a12 * x2;
                acc[1][j] += a13 * x3;
                acc[2][j] += a20 * x0;
                acc[2][j] += a21 * x1;
                acc[2][j] += a22 * x2;
                acc[2][j] += a23 * x3;
                acc[3][j] += a30 * x0;
                acc[3][j] += a31 * x1;
                acc[3][j] += a32 * x2;
                acc[3][j] += a33 * x3;
            }
        }

        for (; k < n; ++k) {
            const std::size_t kk = static_cast<std::size_t>(k);
            const float a0 = A[r0 * nn + kk];
            const float a1 = A[(r0 + 1) * nn + kk];
            const float a2 = A[(r0 + 2) * nn + kk];
            const float a3 = A[(r0 + 3) * nn + kk];
            const float* bp = B + kk * nn + c0;

            #pragma omp simd
            for (std::size_t j = 0; j < cols; ++j) {
                const float x = bp[j];
                acc[0][j] += a0 * x;
                acc[1][j] += a1 * x;
                acc[2][j] += a2 * x;
                acc[3][j] += a3 * x;
            }
        }
    } else {
        for (int k = 0; k < n; ++k) {
            const std::size_t kk = static_cast<std::size_t>(k);
            const float* bp = B + kk * nn + c0;
            for (int rr = 0; rr < rows; ++rr) {
                const float a = A[(r0 + static_cast<std::size_t>(rr)) * nn + kk];
                #pragma omp simd
                for (std::size_t j = 0; j < cols; ++j)
                    acc[rr][j] += a * bp[j];
            }
        }
    }

    for (int rr = 0; rr < rows; ++rr) {
        float* cp = C + (r0 + static_cast<std::size_t>(rr)) * nn + c0;
        #pragma omp simd
        for (std::size_t j = 0; j < cols; ++j)
            cp[j] = acc[rr][j];
    }
}

template <std::size_t WIDTH>
inline void compute_row_group(const float* A, const float* B, float* C,
                              int n, std::size_t nn, std::size_t r0,
                              int rows, std::size_t c0)
{
    int consumed = 0;
    while (rows - consumed >= static_cast<int>(MR)) {
        compute_tile<WIDTH>(A, B, C, n, nn,
                            r0 + static_cast<std::size_t>(consumed),
                            static_cast<int>(MR), c0);
        consumed += static_cast<int>(MR);
    }
    if (consumed < rows) {
        compute_tile<WIDTH>(A, B, C, n, nn,
                            r0 + static_cast<std::size_t>(consumed),
                            rows - consumed, c0);
    }
}

inline void compute_row_block(const float* A, const float* B, float* C,
                              int n, std::size_t nn, long long block,
                              std::size_t full_columns)
{
    const std::size_t r0 = static_cast<std::size_t>(block) * ROW_GROUP;
    int rows = n - static_cast<int>(r0);
    if (rows > ROW_GROUP)
        rows = ROW_GROUP;

    for (std::size_t c0 = 0; c0 < full_columns; c0 += NR)
        compute_row_group<NR>(A, B, C, n, nn, r0, rows, c0);

    if (full_columns < nn)
        compute_row_group<0>(A, B, C, n, nn, r0, rows, full_columns);
}
} // namespace

extern "C" void run(const void* input1, const void* input2, void* output,
                    int n, int parameter, int threads)
{
    (void)parameter;
    if (n <= 0)
        return;

    const float* A = static_cast<const float*>(input1);
    const float* B = static_cast<const float*>(input2);
    float* C = static_cast<float*>(output);
    const std::size_t nn = static_cast<std::size_t>(n);
    const int team = threads > 0 ? threads : 1;
    const long long blocks = (static_cast<long long>(n) + ROW_GROUP - 1) / ROW_GROUP;
    const std::size_t full_columns = (nn / NR) * NR;

    if (team == 1) {
        for (long long block = 0; block < blocks; ++block)
            compute_row_block(A, B, C, n, nn, block, full_columns);
    } else {
        #pragma omp parallel for schedule(static) num_threads(team)
        for (long long block = 0; block < blocks; ++block)
            compute_row_block(A, B, C, n, nn, block, full_columns);
    }
}
