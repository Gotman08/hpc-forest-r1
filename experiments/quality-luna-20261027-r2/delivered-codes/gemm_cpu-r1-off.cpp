#include <algorithm>
#include <cstddef>

static inline void compute_row_block(const float* A, const float* B, float* C,
                                     int n, int r) {
    constexpr int ROWS = 12;
    constexpr int COLS = 16;
    const int rows = std::min(ROWS, n - r);
    const std::size_t stride = static_cast<std::size_t>(n);

    int c = 0;
    for (; rows == ROWS && c <= n - COLS; c += COLS) {
        float acc[ROWS][COLS] = {};
        int k = 0;

        for (; k <= n - 4; k += 4) {
            for (int q = 0; q < 4; ++q) {
                const int kk = k + q;
                const float* brow =
                    B + static_cast<std::size_t>(kk) * stride + c;
                for (int i = 0; i < ROWS; ++i) {
                    const float a =
                        A + static_cast<std::size_t>(r + i) * stride
                        ? A[static_cast<std::size_t>(r + i) * stride + kk]
                        : 0.0f;
                    #pragma omp simd
                    for (int j = 0; j < COLS; ++j)
                        acc[i][j] += a * brow[j];
                }
            }
        }

        for (; k < n; ++k) {
            const float* brow = B + static_cast<std::size_t>(k) * stride + c;
            for (int i = 0; i < ROWS; ++i) {
                const float a = A[static_cast<std::size_t>(r + i) * stride + k];
                #pragma omp simd
                for (int j = 0; j < COLS; ++j)
                    acc[i][j] += a * brow[j];
            }
        }

        for (int i = 0; i < ROWS; ++i) {
            float* crow = C + static_cast<std::size_t>(r + i) * stride + c;
            for (int j = 0; j < COLS; ++j)
                crow[j] = acc[i][j];
        }
    }

    for (; c < n; ++c) {
        for (int i = 0; i < rows; ++i) {
            float sum = 0.0f;
            for (int k = 0; k < n; ++k)
                sum += A[static_cast<std::size_t>(r + i) * stride + k] *
                       B[static_cast<std::size_t>(k) * stride + c];
            C[static_cast<std::size_t>(r + i) * stride + c] = sum;
        }
    }
}

extern "C" void run(const void* input1, const void* input2, void* output,
                    int n, int parameter, int threads) {
    (void)parameter;
    if (n <= 0)
        return;

    const float* A = static_cast<const float*>(input1);
    const float* B = static_cast<const float*>(input2);
    float* C = static_cast<float*>(output);
    constexpr int ROWS = 12;
    const int row_blocks = n / ROWS + (n % ROWS != 0);

    if (threads > 1 && row_blocks > 1) {
        const int team = std::min(threads, row_blocks);
        #pragma omp parallel for schedule(static) num_threads(team)
        for (int block = 0; block < row_blocks; ++block)
            compute_row_block(A, B, C, n, block * ROWS);
    } else {
        for (int block = 0; block < row_blocks; ++block)
            compute_row_block(A, B, C, n, block * ROWS);
    }
}
