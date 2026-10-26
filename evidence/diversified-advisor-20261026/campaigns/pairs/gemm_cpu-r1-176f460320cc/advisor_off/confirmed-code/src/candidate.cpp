#include <cstddef>
#include <cstdlib>
#include <limits>

#if defined(__AVX512F__)
#include <immintrin.h>
#define SIMD_LANES 16
using Simd = __m512;
#define SIMD_ZERO() _mm512_setzero_ps()
#define SIMD_LOAD(p) _mm512_loadu_ps(p)
#define SIMD_BROADCAST(x) _mm512_set1_ps(x)
#define SIMD_STORE(p, x) _mm512_storeu_ps(p, x)
#if defined(__FMA__)
#define SIMD_ACCUM(acc, a, b) _mm512_fmadd_ps(SIMD_BROADCAST(a), (b), (acc))
#define SIMD_ACCUM_VECTOR(acc, a, b) _mm512_fmadd_ps((a), (b), (acc))
#else
#define SIMD_ACCUM(acc, a, b) _mm512_add_ps((acc), _mm512_mul_ps(SIMD_BROADCAST(a), (b)))
#define SIMD_ACCUM_VECTOR(acc, a, b) _mm512_add_ps((acc), _mm512_mul_ps((a), (b)))
#endif
#elif defined(__AVX__)
#include <immintrin.h>
#define SIMD_LANES 8
using Simd = __m256
#define SIMD_ZERO() _mm256_setzero_ps()
#define SIMD_LOAD(p) _mm256_loadu_ps(p)
#define SIMD_BROADCAST(x) _mm256_set1_ps(x)
#define SIMD_STORE(p, x) _mm256_storeu_ps(p, x)
#if defined(__FMA__)
#define SIMD_ACCUM(acc, a, b) _mm256_fmadd_ps(SIMD_BROADCAST(a), (b), (acc))
#define SIMD_ACCUM_VECTOR(acc, a, b) _mm256_fmadd_ps((a), (b), (acc))
#else
#define SIMD_ACCUM(acc, a, b) _mm256_add_ps((acc), _mm256_mul_ps(SIMD_BROADCAST(a), (b)))
#define SIMD_ACCUM_VECTOR(acc, a, b) _mm256_add_ps((acc), _mm256_mul_ps((a), (b)))
#endif
#elif defined(__SSE__)
#include <immintrin.h>
#define SIMD_LANES 4
using Simd = __m128
#define SIMD_ZERO() _mm_setzero_ps()
#define SIMD_LOAD(p) _mm_loadu_ps(p)
#define SIMD_BROADCAST(x) _mm_set1_ps(x)
#define SIMD_STORE(p, x) _mm_storeu_ps(p, x)
#define SIMD_ACCUM(acc, a, b) _mm_add_ps((acc), _mm_mul_ps(SIMD_BROADCAST(a), (b)))
#define SIMD_ACCUM_VECTOR(acc, a, b) _mm_add_ps((acc), _mm_mul_ps((a), (b)))
#else
#define SIMD_LANES 1
#endif

static void multiply_scalar(const float* a, const float* b, float* c, int n) {
    for (int r = 0; r < n; ++r) {
        for (int col = 0; col < n; ++col) {
            float sum = 0.0f;
            for (int k = 0; k < n; ++k) {
                sum += a[static_cast<std::size_t>(r) * n + k] *
                       b[static_cast<std::size_t>(k) * n + col];
            }
            c[static_cast<std::size_t>(r) * n + col] = sum;
        }
    }
}

#if SIMD_LANES > 1
static inline void store_vector(float* dst, Simd value, int count) {
    if (count == SIMD_LANES) {
        SIMD_STORE(dst, value);
    } else {
        float temporary[SIMD_LANES];
        SIMD_STORE(temporary, value);
        for (int lane = 0; lane < count; ++lane) {
            dst[lane] = temporary[lane];
        }
    }
}

static inline void kernel4(const float* a, const float* packed_panel, float* c,
                           int n, int row, int rows, int col, int columns) {
    Simd c0 = SIMD_ZERO();
    Simd c1 = SIMD_ZERO();
    Simd c2 = SIMD_ZERO();
    Simd c3 = SIMD_ZERO();
    for (int k = 0; k < n; ++k) {
        const Simd b = SIMD_LOAD(packed_panel + static_cast<std::size_t>(k) * SIMD_LANES);
        const float a0 = rows > 0 ? a[static_cast<std::size_t>(row) * n + k] : 0.0f;
        const float a1 = rows > 1 ? a[static_cast<std::size_t>(row + 1) * n + k] : 0.0f;
        const float a2 = rows > 2 ? a[static_cast<std::size_t>(row + 2) * n + k] : 0.0f;
        const float a3 = rows > 3 ? a[static_cast<std::size_t>(row + 3) * n + k] : 0.0f;
        c0 = SIMD_ACCUM(c0, a0, b);
        c1 = SIMD_ACCUM(c1, a1, b);
        c2 = SIMD_ACCUM(c2, a2, b);
        c3 = SIMD_ACCUM(c3, a3, b);
    }
    if (rows > 0) store_vector(c + static_cast<std::size_t>(row) * n + col, c0, columns);
    if (rows > 1) store_vector(c + static_cast<std::size_t>(row + 1) * n + col, c1, columns);
    if (rows > 2) store_vector(c + static_cast<std::size_t>(row + 2) * n + col, c2, columns);
    if (rows > 3) store_vector(c + static_cast<std::size_t>(row + 3) * n + col, c3, columns);
}
#else
static inline void kernel4(const float* a, const float* packed_panel, float* c,
                           int n, int row, int rows, int col, int) {
    for (int r = 0; r < rows; ++r) {
        float sum = 0.0f;
        for (int k = 0; k < n; ++k) {
            sum += a[static_cast<std::size_t>(row + r) * n + k] *
                   packed_panel[k];
        }
        c[static_cast<std::size_t>(row + r) * n + col] = sum;
    }
}
#endif

static inline void kernel4x2(const float* a, const float* panel0,
                             const float* panel1, float* c, int n, int row,
                             int rows, int col0, int columns0, int col1,
                             int columns1) {
#if SIMD_LANES > 1
    Simd c00 = SIMD_ZERO();
    Simd c01 = SIMD_ZERO();
    Simd c10 = SIMD_ZERO();
    Simd c11 = SIMD_ZERO();
    Simd c20 = SIMD_ZERO();
    Simd c21 = SIMD_ZERO();
    Simd c30 = SIMD_ZERO();
    Simd c31 = SIMD_ZERO();
    for (int k = 0; k < n; ++k) {
        const Simd b0 = SIMD_LOAD(panel0 + static_cast<std::size_t>(k) * SIMD_LANES);
        const Simd b1 = SIMD_LOAD(panel1 + static_cast<std::size_t>(k) * SIMD_LANES);
        const float a0 = rows > 0 ? a[static_cast<std::size_t>(row) * n + k] : 0.0f;
        const float a1 = rows > 1 ? a[static_cast<std::size_t>(row + 1) * n + k] : 0.0f;
        const float a2 = rows > 2 ? a[static_cast<std::size_t>(row + 2) * n + k] : 0.0f;
        const float a3 = rows > 3 ? a[static_cast<std::size_t>(row + 3) * n + k] : 0.0f;
        const Simd va0 = SIMD_BROADCAST(a0);
        const Simd va1 = SIMD_BROADCAST(a1);
        const Simd va2 = SIMD_BROADCAST(a2);
        const Simd va3 = SIMD_BROADCAST(a3);
        c00 = SIMD_ACCUM_VECTOR(c00, va0, b0);
        c01 = SIMD_ACCUM_VECTOR(c01, va0, b1);
        c10 = SIMD_ACCUM_VECTOR(c10, va1, b0);
        c11 = SIMD_ACCUM_VECTOR(c11, va1, b1);
        c20 = SIMD_ACCUM_VECTOR(c20, va2, b0);
        c21 = SIMD_ACCUM_VECTOR(c21, va2, b1);
        c30 = SIMD_ACCUM_VECTOR(c30, va3, b0);
        c31 = SIMD_ACCUM_VECTOR(c31, va3, b1);
    }
    if (rows > 0) {
        store_vector(c + static_cast<std::size_t>(row) * n + col0, c00, columns0);
        store_vector(c + static_cast<std::size_t>(row) * n + col1, c01, columns1);
    }
    if (rows > 1) {
        store_vector(c + static_cast<std::size_t>(row + 1) * n + col0, c10, columns0);
        store_vector(c + static_cast<std::size_t>(row + 1) * n + col1, c11, columns1);
    }
    if (rows > 2) {
        store_vector(c + static_cast<std::size_t>(row + 2) * n + col0, c20, columns0);
        store_vector(c + static_cast<std::size_t>(row + 2) * n + col1, c21, columns1);
    }
    if (rows > 3) {
        store_vector(c + static_cast<std::size_t>(row + 3) * n + col0, c30, columns0);
        store_vector(c + static_cast<std::size_t>(row + 3) * n + col1, c31, columns1);
    }
#else
    kernel4(a, panel0, c, n, row, rows, col0, columns0);
    kernel4(a, panel1, c, n, row, rows, col1, columns1);
#endif
}

static inline void pack_panel(const float* b, float* packed, int n,
                              std::size_t block, std::size_t width) {
    const std::size_t first_column = block * width;
    float* panel = packed + block * static_cast<std::size_t>(n) * width;
    for (int k = 0; k < n; ++k) {
        float* dst = panel + static_cast<std::size_t>(k) * width;
        for (std::size_t lane = 0; lane < width; ++lane) {
            const std::size_t column = first_column + lane;
            dst[lane] = column < static_cast<std::size_t>(n)
                            ? b[static_cast<std::size_t>(k) * n + column]
                            : 0.0f;
        }
    }
}

static inline int panel_columns(int n, std::size_t block, std::size_t width) {
    const std::size_t first_column = block * width;
    const std::size_t remaining = static_cast<std::size_t>(n) - first_column;
    return static_cast<int>(remaining < width ? remaining : width);
}

static inline void compute_output_tile(const float* a, const float* packed,
                                       float* c, int n, int row_group,
                                       std::size_t tile_group,
                                       std::size_t blocks, std::size_t width) {
    const int row = row_group * 4;
    const int rows = (n - row < 4) ? n - row : 4;
    const std::size_t block = tile_group * 2;
    const std::size_t first_column = block * width;
    const float* panel0 = packed + block * static_cast<std::size_t>(n) * width;
    if (block + 1 < blocks) {
        const std::size_t next_block = block + 1;
        const std::size_t second_column = next_block * width;
        const float* panel1 = packed + next_block * static_cast<std::size_t>(n) * width;
        kernel4x2(a, panel0, panel1, c, n, row, rows,
                  static_cast<int>(first_column), panel_columns(n, block, width),
                  static_cast<int>(second_column),
                  panel_columns(n, next_block, width));
    } else {
        kernel4(a, panel0, c, n, row, rows, static_cast<int>(first_column),
                panel_columns(n, block, width));
    }
}

extern "C" void run(const void* input1, const void* input2, void* output,
                    int n, int parameter, int threads) {
    (void)parameter;
    if (n <= 0) return;

    const float* a = static_cast<const float*>(input1);
    const float* b = static_cast<const float*>(input2);
    float* c = static_cast<float*>(output);

    const std::size_t width = SIMD_LANES;
    const std::size_t n_size = static_cast<std::size_t>(n);
    const std::size_t max_size = std::numeric_limits<std::size_t>::max();
    const std::size_t blocks = n_size / width + (n_size % width != 0);
    if (blocks == 0 || blocks > max_size / width) {
        multiply_scalar(a, b, c, n);
        return;
    }
    const std::size_t padded_columns = blocks * width;
    if (n_size > max_size / padded_columns) {
        multiply_scalar(a, b, c, n);
        return;
    }
    const std::size_t packed_elements = n_size * padded_columns;
    if (packed_elements > max_size / sizeof(float)) {
        multiply_scalar(a, b, c, n);
        return;
    }
    float* packed = static_cast<float*>(std::malloc(packed_elements * sizeof(float)));
    if (packed == nullptr) {
        multiply_scalar(a, b, c, n);
        return;
    }

    const std::size_t tile_groups = blocks / 2 + (blocks % 2 != 0);
    const int row_groups = n / 4 + (n % 4 != 0);
    const long long tile_group_count = static_cast<long long>(tile_groups);
    const long long total_work = static_cast<long long>(row_groups) * tile_group_count;

#if defined(_OPENMP)
    if (threads > 1 && total_work > 1) {
        const int worker_count = total_work < threads
                                     ? static_cast<int>(total_work)
                                     : threads;
#pragma omp parallel num_threads(worker_count)
        {
#pragma omp for schedule(static)
            for (long long block_index = 0;
                 block_index < static_cast<long long>(blocks); ++block_index) {
                pack_panel(b, packed, n, static_cast<std::size_t>(block_index), width);
            }
#pragma omp for schedule(static)
            for (long long task = 0; task < total_work; ++task) {
                const int row_group = static_cast<int>(task / tile_group_count);
                const std::size_t tile_group =
                    static_cast<std::size_t>(task % tile_group_count);
                compute_output_tile(a, packed, c, n, row_group, tile_group,
                                    blocks, width);
            }
        }
    } else {
        for (std::size_t block = 0; block < blocks; ++block) {
            pack_panel(b, packed, n, block, width);
        }
        for (long long task = 0; task < total_work; ++task) {
            const int row_group = static_cast<int>(task / tile_group_count);
            const std::size_t tile_group =
                static_cast<std::size_t>(task % tile_group_count);
            compute_output_tile(a, packed, c, n, row_group, tile_group,
                                blocks, width);
        }
    }
#else
    (void)threads;
    for (std::size_t block = 0; block < blocks; ++block) {
        pack_panel(b, packed, n, block, width);
    }
    for (long long task = 0; task < total_work; ++task) {
        const int row_group = static_cast<int>(task / tile_group_count);
        const std::size_t tile_group =
            static_cast<std::size_t>(task % tile_group_count);
        compute_output_tile(a, packed, c, n, row_group, tile_group,
                            blocks, width);
    }
#endif

    std::free(packed);
}
