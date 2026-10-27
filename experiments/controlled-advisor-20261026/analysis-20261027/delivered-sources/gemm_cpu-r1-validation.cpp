#include <cstddef>

static inline void kernel4x64(const float* A, const float* B, float* C,
                              std::size_t n, std::size_t row,
                              std::size_t col) {
    float acc[4][4][16] = {};
    const float* a0 = A + row * n;
    const float* a1 = a0 + n;
    const float* a2 = a1 + n;
    const float* a3 = a2 + n;

    std::size_t k = 0;
    for (; k + 1 < n; k += 2) {
        const float a00 = a0[k];
        const float a10 = a1[k];
        const float a20 = a2[k];
        const float a30 = a3[k];
        const float a01 = a0[k + 1];
        const float a11 = a1[k + 1];
        const float a21 = a2[k + 1];
        const float a31 = a3[k + 1];

        for (int half = 0; half < 4; ++half) {
            const std::size_t offset = col + static_cast<std::size_t>(half) * 16;
            const float* bp0 = B + k * n + offset;
            const float* bp1 = B + (k + 1) * n + offset;
            #pragma omp simd
            for (int c = 0; c < 16; ++c) {
                const float bv0 = bp0[c];
                const float bv1 = bp1[c];
                acc[0][half][c] += a00 * bv0;
                acc[0][half][c] += a01 * bv1;
                acc[1][half][c] += a10 * bv0;
                acc[1][half][c] += a11 * bv1;
                acc[2][half][c] += a20 * bv0;
                acc[2][half][c] += a21 * bv1;
                acc[3][half][c] += a30 * bv0;
                acc[3][half][c] += a31 * bv1;
            }
        }
    }

    if (k < n) {
        const float av0 = a0[k];
        const float av1 = a1[k];
        const float av2 = a2[k];
        const float av3 = a3[k];
        for (int half = 0; half < 4; ++half) {
            const float* bp = B + k * n + col + static_cast<std::size_t>(half) * 16;
            #pragma omp simd
            for (int c = 0; c < 16; ++c) {
                const float bv = bp[c];
                acc[0][half][c] += av0 * bv;
                acc[1][half][c] += av1 * bv;
                acc[2][half][c] += av2 * bv;
                acc[3][half][c] += av3 * bv;
            }
        }
    }

    for (int r = 0; r < 4; ++r) {
        float* cp = C + (row + static_cast<std::size_t>(r)) * n + col;
        for (int half = 0; half < 4; ++half)
            for (int c = 0; c < 16; ++c)
                cp[half * 16 + c] = acc[r][half][c];
    }
}

static inline float scalar_dot(const float* a, const float* B,
                               std::size_t n, std::size_t col) {
    float sum = 0.0f;
    for (std::size_t k = 0; k < n; ++k)
        sum += a[k] * B[k * n + col];
    return sum;
}

static inline void process_row_tile(const float* A, const float* B, float* C,
                                    std::size_t n, std::size_t row) {
    if (n - row < 4) {
        for (std::size_t r = 0; row + r < n; ++r) {
            const float* ap = A + (row + r) * n;
            for (std::size_t col = 0; col < n; ++col)
                C[(row + r) * n + col] = scalar_dot(ap, B, n, col);
        }
        return;
    }

    const std::size_t full_cols = n - n % 64;
    for (std::size_t col = 0; col < full_cols; col += 64)
        kernel4x64(A, B, C, n, row, col);

    for (std::size_t col = full_cols; col < n; ++col) {
        for (std::size_t r = 0; r < 4; ++r) {
            const float* ap = A + (row + r) * n;
            C[(row + r) * n + col] = scalar_dot(ap, B, n, col);
        }
    }
}

extern "C" void run(const void* input1, const void* input2, void* output,
                    int n, int parameter, int threads) {
    (void)parameter;
    if (n <= 0)
        return;

    const std::size_t size_n = static_cast<std::size_t>(n);
    const float* A = static_cast<const float*>(input1);
    const float* B = static_cast<const float*>(input2);
    float* C = static_cast<float*>(output);
    const int tile_count = n / 4 + (n % 4 != 0);

    if (threads > 1 && tile_count / threads >= 8) {
        #pragma omp parallel for schedule(static) num_threads(threads)
        for (int tile = 0; tile < tile_count; ++tile) {
            const std::size_t row = static_cast<std::size_t>(tile) * 4;
            process_row_tile(A, B, C, size_n, row);
        }
    } else {
        for (int tile = 0; tile < tile_count; ++tile) {
            const std::size_t row = static_cast<std::size_t>(tile) * 4;
            process_row_tile(A, B, C, size_n, row);
        }
    }
}
