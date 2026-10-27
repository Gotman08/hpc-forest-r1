#include <algorithm>
#include <cstddef>

static void compute_single_thread_blocked(const float* A, const float* B,
                                          float* C, int n)
{
    const std::size_t stride = static_cast<std::size_t>(n);
    constexpr int tile = 8;
    const int full = n - (n % tile);

    for (int r = 0; r < full; r += tile) {
        const std::size_t row = static_cast<std::size_t>(r) * stride;
        const float* a0 = A + row;
        const float* a1 = a0 + stride;
        const float* a2 = a1 + stride;
        const float* a3 = a2 + stride;
        const float* a4 = a3 + stride;
        const float* a5 = a4 + stride;
        const float* a6 = a5 + stride;
        const float* a7 = a6 + stride;

        for (int c = 0; c < full; c += tile) {
            float acc[tile][tile] = {};

            for (int k = 0; k < n; ++k) {
                const std::size_t kk = static_cast<std::size_t>(k);
                const float av0 = a0[kk];
                const float av1 = a1[kk];
                const float av2 = a2[kk];
                const float av3 = a3[kk];
                const float av4 = a4[kk];
                const float av5 = a5[kk];
                const float av6 = a6[kk];
                const float av7 = a7[kk];
                const float* brow = B + kk * stride + static_cast<std::size_t>(c);

                #pragma omp simd
                for (int x = 0; x < tile; ++x) {
                    const float bv = brow[x];
                    acc[0][x] += av0 * bv;
                    acc[1][x] += av1 * bv;
                    acc[2][x] += av2 * bv;
                    acc[3][x] += av3 * bv;
                    acc[4][x] += av4 * bv;
                    acc[5][x] += av5 * bv;
                    acc[6][x] += av6 * bv;
                    acc[7][x] += av7 * bv;
                }
            }

            for (int rr = 0; rr < tile; ++rr) {
                float* out = C + row + static_cast<std::size_t>(rr) * stride
                           + static_cast<std::size_t>(c);
                #pragma omp simd
                for (int x = 0; x < tile; ++x)
                    out[x] = acc[rr][x];
            }
        }
    }

    for (int r = 0; r < full; ++r) {
        const std::size_t row = static_cast<std::size_t>(r) * stride;
        for (int c = full; c < n; ++c) {
            float sum = 0.0f;
            for (int k = 0; k < n; ++k)
                sum += A[row + static_cast<std::size_t>(k)]
                     * B[static_cast<std::size_t>(k) * stride
                         + static_cast<std::size_t>(c)];
            C[row + static_cast<std::size_t>(c)] = sum;
        }
    }

    for (int r = full; r < n; ++r) {
        const std::size_t row = static_cast<std::size_t>(r) * stride;
        for (int c = 0; c < n; ++c) {
            float sum = 0.0f;
            for (int k = 0; k < n; ++k)
                sum += A[row + static_cast<std::size_t>(k)]
                     * B[static_cast<std::size_t>(k) * stride
                         + static_cast<std::size_t>(c)];
            C[row + static_cast<std::size_t>(c)] = sum;
        }
    }
}

static constexpr int rows_per_block = 4;

static inline void compute_row_block(const float* A, const float* B, float* C,
                                     int n, int block)
{
    const int first_row = block * rows_per_block;
    const int remaining_rows = n - first_row;
    const int row_count = remaining_rows < rows_per_block
                        ? remaining_rows : rows_per_block;
    const int end_row = first_row + row_count;
    const std::size_t stride = static_cast<std::size_t>(n);

    for (int r = first_row; r < end_row; ++r) {
        const std::size_t row = static_cast<std::size_t>(r) * stride;
        float* c_row = C + row;
        for (int c = 0; c < n; ++c)
            c_row[c] = 0.0f;
    }

    for (int k = 0; k < n; ++k) {
        const float* b_row = B + static_cast<std::size_t>(k) * stride;
        for (int r = first_row; r < end_row; ++r) {
            const std::size_t row = static_cast<std::size_t>(r) * stride;
            const float a = A[row + static_cast<std::size_t>(k)];
            float* c_row = C + row;
            for (int c = 0; c < n; ++c)
                c_row[c] += a * b_row[c];
        }
    }
}

static void compute_row_blocks(const float* A, const float* B, float* C,
                               int n, int team_bound)
{
    const int block_count = n / rows_per_block
                          + ((n % rows_per_block) != 0);
    const int team = std::max(1, std::min(team_bound, block_count));

    if (team == 1) {
        for (int block = 0; block < block_count; ++block)
            compute_row_block(A, B, C, n, block);
    } else {
        #pragma omp parallel for schedule(static) num_threads(team)
        for (int block = 0; block < block_count; ++block)
            compute_row_block(A, B, C, n, block);
    }
}

extern "C" void run(const void* input1, const void* input2, void* output,
                    int n, int parameter, int threads)
{
    (void)parameter;
    if (n <= 0)
        return;

    const float* A = static_cast<const float*>(input1);
    const float* B = static_cast<const float*>(input2);
    float* C = static_cast<float*>(output);

    if (threads <= 1) {
        compute_single_thread_blocked(A, B, C, n);
        return;
    }

    compute_row_blocks(A, B, C, n, threads);
}
