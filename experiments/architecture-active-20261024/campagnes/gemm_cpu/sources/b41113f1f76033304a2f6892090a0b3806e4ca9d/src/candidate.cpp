#include <cstddef>
#include <cstring>

namespace {
constexpr int kRowTile = 8;
constexpr int kColumnTile = 128;
constexpr int kInnerTile = 32;

void update_row_tile(const float* a, const float* b, float* c, int n, int ii) {
    int iend = ii + kRowTile;
    if (iend > n) iend = n;

    // Keep each output-column tile resident while accumulating K in order.
    for (int jj = 0; jj < n; jj += kColumnTile) {
        int jend = jj + kColumnTile;
        if (jend > n) jend = n;

        for (int kk = 0; kk < n; kk += kInnerTile) {
            int kend = kk + kInnerTile;
            if (kend > n) kend = n;

            for (int i = ii; i < iend; ++i) {
                const std::size_t row_offset =
                    static_cast<std::size_t>(i) * static_cast<std::size_t>(n);
                const float* arow = a + row_offset;
                float* crow = c + row_offset;

                for (int k = kk; k < kend; ++k) {
                    const float aik = arow[k];
                    const float* brow = b + static_cast<std::size_t>(k) *
                                            static_cast<std::size_t>(n);
                    for (int j = jj; j < jend; ++j) {
                        crow[j] += aik * brow[j];
                    }
                }
            }
        }
    }
}
}  // namespace

extern "C" void run(const void* input1, const void* input2, void* output,
                    int n, int parameter, int threads) {
    (void)parameter;
    if (n <= 0) return;

    const std::size_t dim = static_cast<std::size_t>(n);
    std::memset(output, 0, dim * dim * sizeof(float));

    int worker_count = threads;
    if (worker_count < 1) worker_count = 1;
    if (worker_count > 8) worker_count = 8;

    const float* a = static_cast<const float*>(input1);
    const float* b = static_cast<const float*>(input2);
    float* c = static_cast<float*>(output);

    if (n >= 256 && worker_count > 1) {
        // Each iteration owns complete, disjoint output rows.
        #pragma omp parallel for schedule(static) num_threads(worker_count)
        for (int ii = 0; ii < n; ii += kRowTile) {
            update_row_tile(a, b, c, n, ii);
        }
    } else {
        for (int ii = 0; ii < n; ii += kRowTile) {
            update_row_tile(a, b, c, n, ii);
        }
    }
}
