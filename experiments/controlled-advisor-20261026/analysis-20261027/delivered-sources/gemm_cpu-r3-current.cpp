#include <cstddef>
#include <omp.h>

template <int Cols>
static inline void kernel8(const float* A, const float* B, float* C,
                           int n, int r0, int c0) {
    float s0[Cols] = {};
    float s1[Cols] = {};
    float s2[Cols] = {};
    float s3[Cols] = {};
    float s4[Cols] = {};
    float s5[Cols] = {};
    float s6[Cols] = {};
    float s7[Cols] = {};
    float b0[Cols];
    float b1[Cols];

    const std::size_t stride = static_cast<std::size_t>(n);
    const std::size_t row0 = static_cast<std::size_t>(r0) * stride;
    const std::size_t col0 = static_cast<std::size_t>(c0);
    int k = 0;
    for (; k + 1 < n; k += 2) {
        const std::size_t kk = static_cast<std::size_t>(k);
        const std::size_t bbase0 = kk * stride + col0;
        const std::size_t bbase1 = (kk + 1) * stride + col0;
        #pragma omp simd
        for (int j = 0; j < Cols; ++j) {
            const std::size_t jj = static_cast<std::size_t>(j);
            b0[j] = B[bbase0 + jj];
            b1[j] = B[bbase1 + jj];
        }

        const float a00 = A[row0 + kk];
        const float a01 = A[row0 + stride + kk];
        const float a02 = A[row0 + 2 * stride + kk];
        const float a03 = A[row0 + 3 * stride + kk];
        const float a04 = A[row0 + 4 * stride + kk];
        const float a05 = A[row0 + 5 * stride + kk];
        const float a06 = A[row0 + 6 * stride + kk];
        const float a07 = A[row0 + 7 * stride + kk];
        const float a10 = A[row0 + kk + 1];
        const float a11 = A[row0 + stride + kk + 1];
        const float a12 = A[row0 + 2 * stride + kk + 1];
        const float a13 = A[row0 + 3 * stride + kk + 1];
        const float a14 = A[row0 + 4 * stride + kk + 1];
        const float a15 = A[row0 + 5 * stride + kk + 1];
        const float a16 = A[row0 + 6 * stride + kk + 1];
        const float a17 = A[row0 + 7 * stride + kk + 1];

        #pragma omp simd
        for (int j = 0; j < Cols; ++j) {
            const float x0 = b0[j];
            const float x1 = b1[j];
            s0[j] += a00 * x0;
            s0[j] += a10 * x1;
            s1[j] += a01 * x0;
            s1[j] += a11 * x1;
            s2[j] += a02 * x0;
            s2[j] += a12 * x1;
            s3[j] += a03 * x0;
            s3[j] += a13 * x1;
            s4[j] += a04 * x0;
            s4[j] += a14 * x1;
            s5[j] += a05 * x0;
            s5[j] += a15 * x1;
            s6[j] += a06 * x0;
            s6[j] += a16 * x1;
            s7[j] += a07 * x0;
            s7[j] += a17 * x1;
        }
    }

    if (k < n) {
        const std::size_t kk = static_cast<std::size_t>(k);
        const std::size_t bbase = kk * stride + col0;
        const float a0 = A[row0 + kk];
        const float a1 = A[row0 + stride + kk];
        const float a2 = A[row0 + 2 * stride + kk];
        const float a3 = A[row0 + 3 * stride + kk];
        const float a4 = A[row0 + 4 * stride + kk];
        const float a5 = A[row0 + 5 * stride + kk];
        const float a6 = A[row0 + 6 * stride + kk];
        const float a7 = A[row0 + 7 * stride + kk];
        #pragma omp simd
        for (int j = 0; j < Cols; ++j) {
            const float b = B[bbase + static_cast<std::size_t>(j)];
            s0[j] += a0 * b;
            s1[j] += a1 * b;
            s2[j] += a2 * b;
            s3[j] += a3 * b;
            s4[j] += a4 * b;
            s5[j] += a5 * b;
            s6[j] += a6 * b;
            s7[j] += a7 * b;
        }
    }

    const std::size_t out0 = row0 + col0;
    for (int j = 0; j < Cols; ++j) {
        const std::size_t jj = static_cast<std::size_t>(j);
        C[out0 + jj] = s0[j];
        C[out0 + stride + jj] = s1[j];
        C[out0 + 2 * stride + jj] = s2[j];
        C[out0 + 3 * stride + jj] = s3[j];
        C[out0 + 4 * stride + jj] = s4[j];
        C[out0 + 5 * stride + jj] = s5[j];
        C[out0 + 6 * stride + jj] = s6[j];
        C[out0 + 7 * stride + jj] = s7[j];
    }
}

template <int Cols>
static inline void kernel1(const float* A, const float* B, float* C,
                           int n, int r, int c0) {
    float sum[Cols] = {};
    float b0[Cols];
    float b1[Cols];
    const std::size_t stride = static_cast<std::size_t>(n);
    const std::size_t row = static_cast<std::size_t>(r) * stride;
    const std::size_t col0 = static_cast<std::size_t>(c0);
    int k = 0;
    for (; k + 1 < n; k += 2) {
        const std::size_t kk = static_cast<std::size_t>(k);
        const std::size_t bbase0 = kk * stride + col0;
        const std::size_t bbase1 = (kk + 1) * stride + col0;
        #pragma omp simd
        for (int j = 0; j < Cols; ++j) {
            const std::size_t jj = static_cast<std::size_t>(j);
            b0[j] = B[bbase0 + jj];
            b1[j] = B[bbase1 + jj];
        }
        const float a0 = A[row + kk];
        const float a1 = A[row + kk + 1];
        #pragma omp simd
        for (int j = 0; j < Cols; ++j) {
            sum[j] += a0 * b0[j];
            sum[j] += a1 * b1[j];
        }
    }
    if (k < n) {
        const std::size_t kk = static_cast<std::size_t>(k);
        const float a = A[row + kk];
        const std::size_t bbase = kk * stride + col0;
        #pragma omp simd
        for (int j = 0; j < Cols; ++j)
            sum[j] += a * B[bbase + static_cast<std::size_t>(j)];
    }
    const std::size_t out = row + col0;
    for (int j = 0; j < Cols; ++j)
        C[out + static_cast<std::size_t>(j)] = sum[j];
}

static inline void process_tile(const float* A, const float* B, float* C,
                                int n, std::size_t col_tiles,
                                long long tile_id) {
    const std::size_t id = static_cast<std::size_t>(tile_id);
    const int r0 = static_cast<int>((id / col_tiles) * 8);
    const int c0 = static_cast<int>((id % col_tiles) * 16);
    const bool full_rows = n - r0 >= 8;
    const bool full_cols = n - c0 >= 16;

    if (full_rows) {
        if (full_cols) {
            kernel8<16>(A, B, C, n, r0, c0);
        } else {
            for (int c = c0; c < n; ++c)
                kernel8<1>(A, B, C, n, r0, c);
        }
    } else {
        for (int r = r0; r < n; ++r) {
            if (full_cols) {
                kernel1<16>(A, B, C, n, r, c0);
            } else {
                for (int c = c0; c < n; ++c)
                    kernel1<1>(A, B, C, n, r, c);
            }
        }
    }
}

extern "C" void run(const void* input1, const void* input2, void* output,
                    int n, int parameter, int threads) {
    (void)parameter;
    if (n <= 0) return;

    const float* A = static_cast<const float*>(input1);
    const float* B = static_cast<const float*>(input2);
    float* C = static_cast<float*>(output);

    const std::size_t dim = static_cast<std::size_t>(n);
    const std::size_t row_tiles = (dim + 7) / 8;
    const std::size_t col_tiles = (dim + 15) / 16;
    const long long total_tiles = static_cast<long long>(row_tiles * col_tiles);

    int workers = threads > 1 ? threads : 1;
    if (static_cast<std::size_t>(workers) > row_tiles * col_tiles)
        workers = static_cast<int>(row_tiles * col_tiles);

    if (workers > 1 && !omp_in_parallel()) {
        #pragma omp parallel for schedule(static) num_threads(workers)
        for (long long tile = 0; tile < total_tiles; ++tile)
            process_tile(A, B, C, n, col_tiles, tile);
    } else {
        for (long long tile = 0; tile < total_tiles; ++tile)
            process_tile(A, B, C, n, col_tiles, tile);
    }
}
