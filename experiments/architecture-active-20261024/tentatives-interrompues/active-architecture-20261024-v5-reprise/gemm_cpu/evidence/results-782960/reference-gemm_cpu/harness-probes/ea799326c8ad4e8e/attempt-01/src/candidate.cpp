#include <algorithm>
#include <cstddef>
#include <cstring>
#include <omp.h>

extern "C" void run(const void* input1, const void* input2, void* output,
                    int n, int parameter, int threads)
{
    (void)parameter;
    if (n <= 0)
        return;

    const float* a = static_cast<const float*>(input1);
    const float* b = static_cast<const float*>(input2);
    float* c = static_cast<float*>(output);
    const std::size_t stride = static_cast<std::size_t>(n);

    // Preserve overwrite semantics on every call.
    std::memset(c, 0, stride * stride * sizeof(float));

    // Each tile owns two output rows and shares each streamed B value between them.
    const int row_tiles = n / 2 + n % 2;
    const int workers = std::min(threads > 1 ? threads : 1, row_tiles);

    #pragma omp parallel for schedule(static) num_threads(workers) if(workers > 1)
    for (int tile = 0; tile < row_tiles; ++tile) {
        const int row0 = tile * 2;
        const bool has_row1 = row0 + 1 < n;
        const float* a0 = a + static_cast<std::size_t>(row0) * stride;
        float* c0 = c + static_cast<std::size_t>(row0) * stride;
        const float* a1 = has_row1 ? a0 + stride : nullptr;
        float* c1 = has_row1 ? c0 + stride : nullptr;

        for (int k = 0; k < n; ++k) {
            const float* b_row = b + static_cast<std::size_t>(k) * stride;
            const float scale0 = a0[k];

            if (has_row1) {
                const float scale1 = a1[k];
                for (int col = 0; col < n; ++col) {
                    const float value = b_row[col];
                    c0[col] += scale0 * value;
                    c1[col] += scale1 * value;
                }
            } else {
                for (int col = 0; col < n; ++col)
                    c0[col] += scale0 * b_row[col];
            }
        }
    }
}
