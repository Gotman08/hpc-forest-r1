#include <algorithm>
#include <cstddef>
#include <cstdlib>
#include <cstring>
#include <omp.h>

#if defined(__x86_64__) || defined(__i386__)
#include <immintrin.h>

static __attribute__((target("avx512f,fma"))) void kernel8x16(
    const float* a, const float* b, float* c,
    int lda, int ldb, int ldc, int kc)
{
    __m512 c0 = _mm512_loadu_ps(c + 0 * ldc);
    __m512 c1 = _mm512_loadu_ps(c + 1 * ldc);
    __m512 c2 = _mm512_loadu_ps(c + 2 * ldc);
    __m512 c3 = _mm512_loadu_ps(c + 3 * ldc);
    __m512 c4 = _mm512_loadu_ps(c + 4 * ldc);
    __m512 c5 = _mm512_loadu_ps(c + 5 * ldc);
    __m512 c6 = _mm512_loadu_ps(c + 6 * ldc);
    __m512 c7 = _mm512_loadu_ps(c + 7 * ldc);

#define GEMM_FMA_ROW(acc, row) \
    acc = _mm512_fmadd_ps(_mm512_set1_ps(a[(std::size_t)(row) * lda + k]), bv, acc)
    for (int k = 0; k < kc; ++k) {
        const __m512 bv = _mm512_loadu_ps(b + (std::size_t)k * ldb);
        GEMM_FMA_ROW(c0, 0);
        GEMM_FMA_ROW(c1, 1);
        GEMM_FMA_ROW(c2, 2);
        GEMM_FMA_ROW(c3, 3);
        GEMM_FMA_ROW(c4, 4);
        GEMM_FMA_ROW(c5, 5);
        GEMM_FMA_ROW(c6, 6);
        GEMM_FMA_ROW(c7, 7);
    }
#undef GEMM_FMA_ROW

    _mm512_storeu_ps(c + 0 * ldc, c0);
    _mm512_storeu_ps(c + 1 * ldc, c1);
    _mm512_storeu_ps(c + 2 * ldc, c2);
    _mm512_storeu_ps(c + 3 * ldc, c3);
    _mm512_storeu_ps(c + 4 * ldc, c4);
    _mm512_storeu_ps(c + 5 * ldc, c5);
    _mm512_storeu_ps(c + 6 * ldc, c6);
    _mm512_storeu_ps(c + 7 * ldc, c7);
}

static bool cpu_has_avx512_fma()
{
    __builtin_cpu_init();
    return __builtin_cpu_supports("avx512f") && __builtin_cpu_supports("fma");
}

static void direct_simd(const float* a, const float* b, float* c,
                        int n, int full_rows, int full_cols, int workers)
{
    const int row_tiles = full_rows / 8;
    const int col_tiles = full_cols / 16;
    const int jobs = row_tiles * col_tiles;
#pragma omp parallel for schedule(static) num_threads(workers) if(n >= 128)
    for (int job = 0; job < jobs; ++job) {
        const int tile_row = job / col_tiles;
        const int tile_col = job % col_tiles;
        const int i = tile_row * 8;
        const int j = tile_col * 16;
        kernel8x16(a + (std::size_t)i * n, b + j,
                   c + (std::size_t)i * n + j, n, n, n, n);
    }
}
#endif

static void scalar_all(const float* a, const float* b, float* c,
                       int n, int workers)
{
#pragma omp parallel for schedule(static) num_threads(workers) if(n >= 128)
    for (int i = 0; i < n; ++i) {
        float* ci = c + (std::size_t)i * n;
        for (int k = 0; k < n; ++k) {
            const float aik = a[(std::size_t)i * n + k];
            const float* bk = b + (std::size_t)k * n;
            for (int j = 0; j < n; ++j)
                ci[j] += aik * bk[j];
        }
    }
}

static void scalar_edges(const float* a, const float* b, float* c,
                         int n, int full_rows, int full_cols, int workers)
{
    if (full_rows == n && full_cols == n)
        return;
#pragma omp parallel for schedule(static) num_threads(workers) if(n >= 128)
    for (int i = 0; i < n; ++i) {
        const int first_col = (i < full_rows) ? full_cols : 0;
        for (int j = first_col; j < n; ++j) {
            float sum = 0.0f;
            for (int k = 0; k < n; ++k)
                sum += a[(std::size_t)i * n + k] * b[(std::size_t)k * n + j];
            c[(std::size_t)i * n + j] = sum;
        }
    }
}

extern "C" void run(const void* input1, const void* input2, void* output,
                    int n, int parameter, int threads)
{
    (void)parameter;
    if (n <= 0)
        return;

    const float* a = static_cast<const float*>(input1);
    const float* b = static_cast<const float*>(input2);
    float* c = static_cast<float*>(output);
    std::memset(c, 0, (std::size_t)n * n * sizeof(float));

    int workers = threads;
    if (workers < 1) workers = 1;
    if (workers > 8) workers = 8;

#if defined(__x86_64__) || defined(__i386__)
    if (!cpu_has_avx512_fma()) {
        scalar_all(a, b, c, n, workers);
        return;
    }

    const int full_rows = (n / 8) * 8;
    const int full_cols = (n / 16) * 16;
    const int row_tiles = full_rows / 8;

    if (n < 256) {
        direct_simd(a, b, c, n, full_rows, full_cols, workers);
        scalar_edges(a, b, c, n, full_rows, full_cols, workers);
        return;
    }

    const int block_k = 128;
    const int block_n = 128;
    const std::size_t a_panel_count = (std::size_t)full_rows * block_k;
    float* a_panel = static_cast<float*>(std::malloc(a_panel_count * sizeof(float)));
    float* b_panel = static_cast<float*>(std::malloc((std::size_t)block_k * block_n * sizeof(float)));
    if (a_panel == nullptr || b_panel == nullptr) {
        std::free(a_panel);
        std::free(b_panel);
        direct_simd(a, b, c, n, full_rows, full_cols, workers);
        scalar_edges(a, b, c, n, full_rows, full_cols, workers);
        return;
    }

#pragma omp parallel num_threads(workers)
    {
        for (int kb = 0; kb < n; kb += block_k) {
            const int klen = std::min(block_k, n - kb);

#pragma omp for schedule(static)
            for (int tile_row = 0; tile_row < row_tiles; ++tile_row) {
                for (int r = 0; r < 8; ++r) {
                    const int row = tile_row * 8 + r;
                    float* dst = a_panel + (std::size_t)row * block_k;
                    const float* src = a + (std::size_t)row * n + kb;
                    std::memcpy(dst, src, (std::size_t)klen * sizeof(float));
                }
            }

            for (int jb = 0; jb < full_cols; jb += block_n) {
                const int jlen = std::min(block_n, full_cols - jb);
                const int col_tiles = jlen / 16;

#pragma omp single
                {
                    for (int kk = 0; kk < klen; ++kk) {
                        float* dst = b_panel + (std::size_t)kk * block_n;
                        const float* src = b + (std::size_t)(kb + kk) * n + jb;
                        std::memcpy(dst, src, (std::size_t)jlen * sizeof(float));
                        if (jlen < block_n)
                            std::memset(dst + jlen, 0,
                                        (std::size_t)(block_n - jlen) * sizeof(float));
                    }
                }

                const int jobs = row_tiles * col_tiles;
#pragma omp for schedule(static)
                for (int job = 0; job < jobs; ++job) {
                    const int tile_row = job / col_tiles;
                    const int tile_col = job % col_tiles;
                    const int i = tile_row * 8;
                    const int j = jb + tile_col * 16;
                    const float* ap = a_panel + (std::size_t)i * block_k;
                    const float* bp = b_panel + tile_col * 16;
                    float* cp = c + (std::size_t)i * n + j;
                    kernel8x16(ap, bp, cp, block_k, block_n, n, klen);
                }
            }
        }
    }

    std::free(a_panel);
    std::free(b_panel);
    scalar_edges(a, b, c, n, full_rows, full_cols, workers);
#else
    scalar_all(a, b, c, n, workers);
#endif
}
