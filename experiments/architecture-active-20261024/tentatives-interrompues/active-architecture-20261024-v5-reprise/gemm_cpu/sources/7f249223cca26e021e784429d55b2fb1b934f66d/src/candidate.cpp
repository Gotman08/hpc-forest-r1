#include <algorithm>
#include <cstddef>
#include <cstring>
#include <omp.h>

namespace {
inline void update_row(const float* A, const float* B, float* C, int n, int r) {
    const std::size_t width = static_cast<std::size_t>(n);
    const std::size_t offset = static_cast<std::size_t>(r) * width;
    const float* arow = A + offset;
    float* crow = C + offset;

    for (int k = 0; k < n; ++k) {
        const float aik = arow[k];
        const float* brow = B + static_cast<std::size_t>(k) * width;
#pragma omp simd
        for (int c = 0; c < n; ++c) {
            crow[c] += aik * brow[c];
        }
    }
}

void multiply(const float* A, const float* B, float* C, int n, int threads) {
    const int workers = threads > 0 ? std::min(threads, n) : 1;
    if (workers > 1) {
#pragma omp parallel for schedule(static) num_threads(workers)
        for (int r = 0; r < n; ++r) {
            update_row(A, B, C, n, r);
        }
    } else {
        for (int r = 0; r < n; ++r) {
            update_row(A, B, C, n, r);
        }
    }
}
}  // namespace

extern "C" void run(const void* input1, const void* input2, void* output,
                    int n, int parameter, int threads) {
    if (n <= 0) {
        return;
    }

    const std::size_t width = static_cast<std::size_t>(n);
    std::memset(output, 0, width * width * sizeof(float));
    multiply(static_cast<const float*>(input1),
             static_cast<const float*>(input2),
             static_cast<float*>(output), n, threads);
}
