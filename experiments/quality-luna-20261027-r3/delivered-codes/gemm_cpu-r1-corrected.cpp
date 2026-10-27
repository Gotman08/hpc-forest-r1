#include <cstddef>
#include <omp.h>

namespace {

const int kRowsPerTile = 8;

void compute_row_tile(const float* A, const float* B, float* C, int n, int tile) {
    const int row_begin = tile * kRowsPerTile;
    const int row_end = (row_begin + kRowsPerTile < n) ? row_begin + kRowsPerTile : n;
    const std::size_t width = static_cast<std::size_t>(n);

    for (int r = row_begin; r < row_end; ++r) {
        const std::size_t row = static_cast<std::size_t>(r) * width;
        for (int c = 0; c < n; ++c) {
            C[row + static_cast<std::size_t>(c)] = 0.0f;
        }
    }

    for (int k = 0; k < n; ++k) {
        const std::size_t b_row = static_cast<std::size_t>(k) * width;
        for (int r = row_begin; r < row_end; ++r) {
            const std::size_t row = static_cast<std::size_t>(r) * width;
            const float a = A[row + static_cast<std::size_t>(k)];
            #pragma omp simd
            for (int c = 0; c < n; ++c) {
                C[row + static_cast<std::size_t>(c)] +=
                    a * B[b_row + static_cast<std::size_t>(c)];
            }
        }
    }
}

} // namespace

extern "C" void run(const void* input1, const void* input2, void* output,
                    int n, int parameter, int threads) {
    (void)parameter;
    if (n <= 0) {
        return;
    }

    const float* A = static_cast<const float*>(input1);
    const float* B = static_cast<const float*>(input2);
    float* C = static_cast<float*>(output);
    const int tile_count = 1 + (n - 1) / kRowsPerTile;

    if (threads <= 1 || tile_count <= 1 || omp_in_parallel()) {
        for (int tile = 0; tile < tile_count; ++tile) {
            compute_row_tile(A, B, C, n, tile);
        }
        return;
    }

    int team_size = threads;
    const int runtime_limit = omp_get_max_threads();
    if (team_size > runtime_limit) {
        team_size = runtime_limit;
    }
    if (team_size > tile_count) {
        team_size = tile_count;
    }

    if (team_size <= 1) {
        for (int tile = 0; tile < tile_count; ++tile) {
            compute_row_tile(A, B, C, n, tile);
        }
    } else {
        #pragma omp parallel for schedule(static) num_threads(team_size)
        for (int tile = 0; tile < tile_count; ++tile) {
            compute_row_tile(A, B, C, n, tile);
        }
    }
}
