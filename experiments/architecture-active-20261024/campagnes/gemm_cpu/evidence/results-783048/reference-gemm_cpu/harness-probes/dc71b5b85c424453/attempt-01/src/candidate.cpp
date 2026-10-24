#include <cstddef>
#include <cstring>

namespace {
constexpr int ROW_TILE = 4;
constexpr int K_TILE = 16;
constexpr int COL_TILE = 256;

inline void accumulate_row_tile(const float* a, const float* b, float* c,
                               int n, int i0) {
    const int i_end = n - i0 < ROW_TILE ? n : i0 + ROW_TILE;

    // K-major tile traversal; the innermost output-column loop is contiguous.
    for (int k0 = 0; k0 < n;) {
        const int k_end = n - k0 < K_TILE ? n : k0 + K_TILE;
        for (int j0 = 0; j0 < n;) {
            const int j_end = n - j0 < COL_TILE ? n : j0 + COL_TILE;
            for (int i = i0; i < i_end; ++i) {
                const std::size_t row_offset = static_cast<std::size_t>(i) * n;
                const float* a_row = a + row_offset;
                float* c_row = c + row_offset;
                for (int k = k0; k < k_end; ++k) {
                    const float a_value = a_row[k];
                    const float* b_row = b + static_cast<std::size_t>(k) * n;
                    for (int j = j0; j < j_end; ++j) {
                        c_row[j] += a_value * b_row[j];
                    }
                }
            }
            j0 = j_end;
        }
        k0 = k_end;
    }
}
}  // namespace

extern "C" void run(const void* input1, const void* input2, void* output,
                     int n, int parameter, int threads) {
    (void)parameter;
    if (n <= 0) {
        return;
    }

    const std::size_t elements = static_cast<std::size_t>(n) *
                                 static_cast<std::size_t>(n);
    std::memset(output, 0, elements * sizeof(float));

    const float* a = static_cast<const float*>(input1);
    const float* b = static_cast<const float*>(input2);
    float* c = static_cast<float*>(output);

    int worker_count = threads;
    if (worker_count < 1) worker_count = 1;
    if (worker_count > 8) worker_count = 8;

    const int row_tile_count = n / ROW_TILE + (n % ROW_TILE != 0);
    if (n >= 256 && worker_count > 1) {
        // Each static work item owns a disjoint set of output rows.
        #pragma omp parallel for schedule(static) num_threads(worker_count)
        for (int tile = 0; tile < row_tile_count; ++tile) {
            accumulate_row_tile(a, b, c, n, tile * ROW_TILE);
        }
    } else {
        // Avoid entering an OpenMP region for small or single-threaded calls.
        for (int tile = 0; tile < row_tile_count; ++tile) {
            accumulate_row_tile(a, b, c, n, tile * ROW_TILE);
        }
    }
}
