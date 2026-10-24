#include <algorithm>
#include <cstddef>
#include <cstring>

static inline void update_tile(const float* a, const float* b, float* c, int n, int tile) {
    const std::size_t stride = static_cast<std::size_t>(n);
    const int first_row = tile * 4;
    const int row_count = std::min(4, n - first_row);

    if (row_count == 4) {
        for (int k = 0; k < n; ++k) {
            const std::size_t k_index = static_cast<std::size_t>(k);
            const std::size_t a_index = static_cast<std::size_t>(first_row) * stride + k_index;
            const float a0 = a[a_index];
            const float a1 = a[a_index + stride];
            const float a2 = a[a_index + 2 * stride];
            const float a3 = a[a_index + 3 * stride];
            const float* b_row = b + k_index * stride;
            float* c0 = c + static_cast<std::size_t>(first_row) * stride;
            float* c1 = c0 + stride;
            float* c2 = c1 + stride;
            float* c3 = c2 + stride;

            #pragma omp simd
            for (int col = 0; col < n; ++col) {
                const float b_value = b_row[col];
                c0[col] += a0 * b_value;
                c1[col] += a1 * b_value;
                c2[col] += a2 * b_value;
                c3[col] += a3 * b_value;
            }
        }
    } else {
        for (int k = 0; k < n; ++k) {
            const std::size_t k_index = static_cast<std::size_t>(k);
            const float* b_row = b + k_index * stride;
            for (int row_offset = 0; row_offset < row_count; ++row_offset) {
                const std::size_t row_index = static_cast<std::size_t>(first_row + row_offset) * stride;
                const float a_value = a[row_index + k_index];
                float* c_row = c + row_index;

                #pragma omp simd
                for (int col = 0; col < n; ++col) {
                    c_row[col] += a_value * b_row[col];
                }
            }
        }
    }
}

extern "C" void run(const void* input1, const void* input2, void* output,
                    int n, int parameter, int threads) {
    (void)parameter;
    if (n <= 0) {
        return;
    }

    const std::size_t stride = static_cast<std::size_t>(n);
    std::memset(output, 0, stride * stride * sizeof(float));

    const float* a = static_cast<const float*>(input1);
    const float* b = static_cast<const float*>(input2);
    float* c = static_cast<float*>(output);
    const int row_tiles = (n - 1) / 4 + 1;
    const int worker_count = std::min(std::max(threads, 1), row_tiles);

    if (worker_count == 1) {
        for (int tile = 0; tile < row_tiles; ++tile) {
            update_tile(a, b, c, n, tile);
        }
    } else {
        #pragma omp parallel for schedule(static) num_threads(worker_count)
        for (int tile = 0; tile < row_tiles; ++tile) {
            update_tile(a, b, c, n, tile);
        }
    }
}
