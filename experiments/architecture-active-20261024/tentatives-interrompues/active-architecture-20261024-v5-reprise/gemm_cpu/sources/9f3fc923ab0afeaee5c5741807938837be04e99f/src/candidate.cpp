#include <cstddef>
#include <memory>

static inline void update_tile_4x4_packed(const float* a, const float* packed_b,
                                          float* c, int n, int row, int col,
                                          int panel_col_start, int panel_stride,
                                          int k_begin, int k_end, bool initialize)
{
    const std::size_t ld = static_cast<std::size_t>(n);
    const std::size_t row0 = static_cast<std::size_t>(row) * ld;
    const std::size_t row1 = row0 + ld;
    const std::size_t row2 = row1 + ld;
    const std::size_t row3 = row2 + ld;
    const std::size_t panel_col = static_cast<std::size_t>(col - panel_col_start);
    const std::size_t c0 = row0 + static_cast<std::size_t>(col);
    const std::size_t c1 = row1 + static_cast<std::size_t>(col);
    const std::size_t c2 = row2 + static_cast<std::size_t>(col);
    const std::size_t c3 = row3 + static_cast<std::size_t>(col);

    float x00 = initialize ? 0.0f : c[c0];
    float x01 = initialize ? 0.0f : c[c0 + 1];
    float x02 = initialize ? 0.0f : c[c0 + 2];
    float x03 = initialize ? 0.0f : c[c0 + 3];
    float x10 = initialize ? 0.0f : c[c1];
    float x11 = initialize ? 0.0f : c[c1 + 1];
    float x12 = initialize ? 0.0f : c[c1 + 2];
    float x13 = initialize ? 0.0f : c[c1 + 3];
    float x20 = initialize ? 0.0f : c[c2];
    float x21 = initialize ? 0.0f : c[c2 + 1];
    float x22 = initialize ? 0.0f : c[c2 + 2];
    float x23 = initialize ? 0.0f : c[c2 + 3];
    float x30 = initialize ? 0.0f : c[c3];
    float x31 = initialize ? 0.0f : c[c3 + 1];
    float x32 = initialize ? 0.0f : c[c3 + 2];
    float x33 = initialize ? 0.0f : c[c3 + 3];

    for (int k = k_begin; k < k_end; ++k) {
        const std::size_t ku = static_cast<std::size_t>(k);
        const float a0 = a[row0 + ku];
        const float a1 = a[row1 + ku];
        const float a2 = a[row2 + ku];
        const float a3 = a[row3 + ku];
        const std::size_t b_row = static_cast<std::size_t>(k - k_begin) *
                                      static_cast<std::size_t>(panel_stride) +
                                  panel_col;
        const float b0 = packed_b[b_row];
        const float b1 = packed_b[b_row + 1];
        const float b2 = packed_b[b_row + 2];
        const float b3 = packed_b[b_row + 3];

        x00 += a0 * b0;
        x01 += a0 * b1;
        x02 += a0 * b2;
        x03 += a0 * b3;
        x10 += a1 * b0;
        x11 += a1 * b1;
        x12 += a1 * b2;
        x13 += a1 * b3;
        x20 += a2 * b0;
        x21 += a2 * b1;
        x22 += a2 * b2;
        x23 += a2 * b3;
        x30 += a3 * b0;
        x31 += a3 * b1;
        x32 += a3 * b2;
        x33 += a3 * b3;
    }

    c[c0] = x00;
    c[c0 + 1] = x01;
    c[c0 + 2] = x02;
    c[c0 + 3] = x03;
    c[c1] = x10;
    c[c1 + 1] = x11;
    c[c1 + 2] = x12;
    c[c1 + 3] = x13;
    c[c2] = x20;
    c[c2 + 1] = x21;
    c[c2 + 2] = x22;
    c[c2 + 3] = x23;
    c[c3] = x30;
    c[c3 + 1] = x31;
    c[c3 + 2] = x32;
    c[c3 + 3] = x33;
}

extern "C" void run(const void* input1, const void* input2, void* output,
                     int n, int parameter, int threads)
{
    (void)parameter;
    (void)threads;
    if (n <= 0) {
        return;
    }

    const float* a = static_cast<const float*>(input1);
    const float* b = static_cast<const float*>(input2);
    float* c = static_cast<float*>(output);
    const int row_block = 32;
    const int col_block = 64;
    const int reduction_block = 64;
    std::unique_ptr<float[]> packed_b(
        new float[static_cast<std::size_t>(reduction_block) *
                  static_cast<std::size_t>(col_block)]);
    const std::size_t ld = static_cast<std::size_t>(n);

    for (int ii = 0; ii < n; ii += row_block) {
        const int i_end = ii + ((n - ii < row_block) ? n - ii : row_block);
        const int i4_end = ii + ((i_end - ii) / 4) * 4;
        for (int jj = 0; jj < n; jj += col_block) {
            const int j_end = jj + ((n - jj < col_block) ? n - jj : col_block);
            const int j4_end = jj + ((j_end - jj) / 4) * 4;
            for (int kk = 0; kk < n; kk += reduction_block) {
                const int k_end = kk + ((n - kk < reduction_block) ? n - kk : reduction_block);
                const bool initialize = (kk == 0);

                for (int k = kk; k < k_end; ++k) {
                    const std::size_t source_row = static_cast<std::size_t>(k) * ld +
                                                   static_cast<std::size_t>(jj);
                    const std::size_t packed_row =
                        static_cast<std::size_t>(k - kk) *
                        static_cast<std::size_t>(col_block);
                    for (int j = jj; j < j_end; ++j) {
                        const std::size_t panel_col = static_cast<std::size_t>(j - jj);
                        packed_b[packed_row + panel_col] = b[source_row + panel_col];
                    }
                }

                for (int i = ii; i < i4_end; i += 4) {
                    for (int j = jj; j < j4_end; j += 4) {
                        update_tile_4x4_packed(a, packed_b.get(), c, n, i, j,
                                               jj, col_block, kk, k_end, initialize);
                    }
                }

                for (int i = ii; i < i_end; ++i) {
                    for (int j = jj; j < j_end; ++j) {
                        if (i < i4_end && j < j4_end) {
                            continue;
                        }
                        const std::size_t index = static_cast<std::size_t>(i) * ld +
                                                  static_cast<std::size_t>(j);
                        float sum = initialize ? 0.0f : c[index];
                        for (int k = kk; k < k_end; ++k) {
                            const std::size_t packed_index =
                                static_cast<std::size_t>(k - kk) *
                                    static_cast<std::size_t>(col_block) +
                                static_cast<std::size_t>(j - jj);
                            sum += a[static_cast<std::size_t>(i) * ld +
                                     static_cast<std::size_t>(k)] * packed_b[packed_index];
                        }
                        c[index] = sum;
                    }
                }
            }
        }
    }
}
