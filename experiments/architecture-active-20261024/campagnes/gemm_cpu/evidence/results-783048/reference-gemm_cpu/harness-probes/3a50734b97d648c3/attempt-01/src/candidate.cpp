#include <algorithm>
#include <cstddef>
#include <cstdlib>
#include <cstring>
#include <omp.h>

#if defined(__GNUC__) && (defined(__x86_64__) || defined(__i386__))
#include <immintrin.h>

static __attribute__((target("avx512f,fma"))) void kernel8x32(
    const float* a, const float* b, float* c,
    int lda, int ldb, int ldc, int kc, int cols, bool accumulate)
{
    const int low_cols = std::min(cols, 16);
    const int high_cols = cols > 16 ? cols - 16 : 0;
    const __mmask16 low_mask = static_cast<__mmask16>((1u << low_cols) - 1u);
    const __mmask16 high_mask = static_cast<__mmask16>((1u << high_cols) - 1u);
    const bool has_high = high_cols != 0;

    __m512 c0l = accumulate ? _mm512_maskz_loadu_ps(low_mask, c + 0 * ldc) : _mm512_setzero_ps();
    __m512 c1l = accumulate ? _mm512_maskz_loadu_ps(low_mask, c + 1 * ldc) : _mm512_setzero_ps();
    __m512 c2l = accumulate ? _mm512_maskz_loadu_ps(low_mask, c + 2 * ldc) : _mm512_setzero_ps();
    __m512 c3l = accumulate ? _mm512_maskz_loadu_ps(low_mask, c + 3 * ldc) : _mm512_setzero_ps();
    __m512 c4l = accumulate ? _mm512_maskz_loadu_ps(low_mask, c + 4 * ldc) : _mm512_setzero_ps();
    __m512 c5l = accumulate ? _mm512_maskz_loadu_ps(low_mask, c + 5 * ldc) : _mm512_setzero_ps();
    __m512 c6l = accumulate ? _mm512_maskz_loadu_ps(low_mask, c + 6 * ldc) : _mm512_setzero_ps();
    __m512 c7l = accumulate ? _mm512_maskz_loadu_ps(low_mask, c + 7 * ldc) : _mm512_setzero_ps();
    __m512 c0h = _mm512_setzero_ps();
    __m512 c1h = _mm512_setzero_ps();
    __m512 c2h = _mm512_setzero_ps();
    __m512 c3h = _mm512_setzero_ps();
    __m512 c4h = _mm512_setzero_ps();
    __m512 c5h = _mm512_setzero_ps();
    __m512 c6h = _mm512_setzero_ps();
    __m512 c7h = _mm512_setzero_ps();

    if (accumulate && has_high) {
        c0h = _mm512_maskz_loadu_ps(high_mask, c + 0 * ldc + 16);
        c1h = _mm512_maskz_loadu_ps(high_mask, c + 1 * ldc + 16);
        c2h = _mm512_maskz_loadu_ps(high_mask, c + 2 * ldc + 16);
        c3h = _mm512_maskz_loadu_ps(high_mask, c + 3 * ldc + 16);
        c4h = _mm512_maskz_loadu_ps(high_mask, c + 4 * ldc + 16);
        c5h = _mm512_maskz_loadu_ps(high_mask, c + 5 * ldc + 16);
        c6h = _mm512_maskz_loadu_ps(high_mask, c + 6 * ldc + 16);
        c7h = _mm512_maskz_loadu_ps(high_mask, c + 7 * ldc + 16);
    }

    for (int k = 0; k < kc; ++k) {
        const std::size_t b_offset = static_cast<std::size_t>(k) * ldb;
        const __m512 b_low = _mm512_maskz_loadu_ps(low_mask, b + b_offset);
        __m512 b_high = _mm512_setzero_ps();
        if (has_high)
            b_high = _mm512_maskz_loadu_ps(high_mask, b + b_offset + 16);

        const __m512 a0 = _mm512_set1_ps(a[k]);
        const __m512 a1 = _mm512_set1_ps(a[lda + k]);
        const __m512 a2 = _mm512_set1_ps(a[2 * lda + k]);
        const __m512 a3 = _mm512_set1_ps(a[3 * lda + k]);
        const __m512 a4 = _mm512_set1_ps(a[4 * lda + k]);
        const __m512 a5 = _mm512_set1_ps(a[5 * lda + k]);
        const __m512 a6 = _mm512_set1_ps(a[6 * lda + k]);
        const __m512 a7 = _mm512_set1_ps(a[7 * lda + k]);

        c0l = _mm512_fmadd_ps(a0, b_low, c0l);
        c1l = _mm512_fmadd_ps(a1, b_low, c1l);
        c2l = _mm512_fmadd_ps(a2, b_low, c2l);
        c3l = _mm512_fmadd_ps(a3, b_low, c3l);
        c4l = _mm512_fmadd_ps(a4, b_low, c4l);
        c5l = _mm512_fmadd_ps(a5, b_low, c5l);
        c6l = _mm512_fmadd_ps(a6, b_low, c6l);
        c7l = _mm512_fmadd_ps(a7, b_low, c7l);
        if (has_high) {
            c0h = _mm512_fmadd_ps(a0, b_high, c0h);
            c1h = _mm512_fmadd_ps(a1, b_high, c1h);
            c2h = _mm512_fmadd_ps(a2, b_high, c2h);
            c3h = _mm512_fmadd_ps(a3, b_high, c3h);
            c4h = _mm512_fmadd_ps(a4, b_high, c4h);
            c5h = _mm512_fmadd_ps(a5, b_high, c5h);
            c6h = _mm512_fmadd_ps(a6, b_high, c6h);
            c7h = _mm512_fmadd_ps(a7, b_high, c7h);
        }
    }

    _mm512_mask_storeu_ps(c + 0 * ldc, low_mask, c0l);
    _mm512_mask_storeu_ps(c + 1 * ldc, low_mask, c1l);
    _mm512_mask_storeu_ps(c + 2 * ldc, low_mask, c2l);
    _mm512_mask_storeu_ps(c + 3 * ldc, low_mask, c3l);
    _mm512_mask_storeu_ps(c + 4 * ldc, low_mask, c4l);
    _mm512_mask_storeu_ps(c + 5 * ldc, low_mask, c5l);
    _mm512_mask_storeu_ps(c + 6 * ldc, low_mask, c6l);
    _mm512_mask_storeu_ps(c + 7 * ldc, low_mask, c7l);
    if (has_high) {
        _mm512_mask_storeu_ps(c + 0 * ldc + 16, high_mask, c0h);
        _mm512_mask_storeu_ps(c + 1 * ldc + 16, high_mask, c1h);
        _mm512_mask_storeu_ps(c + 2 * ldc + 16, high_mask, c2h);
        _mm512_mask_storeu_ps(c + 3 * ldc + 16, high_mask, c3h);
        _mm512_mask_storeu_ps(c + 4 * ldc + 16, high_mask, c4h);
        _mm512_mask_storeu_ps(c + 5 * ldc + 16, high_mask, c5h);
        _mm512_mask_storeu_ps(c + 6 * ldc + 16, high_mask, c6h);
        _mm512_mask_storeu_ps(c + 7 * ldc + 16, high_mask, c7h);
    }
}

static bool cpu_has_avx512_fma()
{
    __builtin_cpu_init();
    return __builtin_cpu_supports("avx512f") && __builtin_cpu_supports("fma");
}

static inline void direct_simd_tile(const float* a, const float* b, float* c,
                                    int n, int col_tiles, int job)
{
    const int tile_row = job / col_tiles;
    const int tile_col = job % col_tiles;
    const int i = tile_row * 8;
    const int j = tile_col * 32;
    kernel8x32(a + static_cast<std::size_t>(i) * n, b + j,
               c + static_cast<std::size_t>(i) * n + j,
               n, n, n, n, 32, false);
}

static void direct_simd(const float* a, const float* b, float* c,
                        int n, int full_rows, int full_cols, int workers,
                        bool parallel)
{
    const int row_tiles = full_rows / 8;
    const int col_tiles = full_cols / 32;
    const int jobs = row_tiles * col_tiles;
    if (parallel) {
#pragma omp parallel for schedule(static) num_threads(workers)
        for (int job = 0; job < jobs; ++job)
            direct_simd_tile(a, b, c, n, col_tiles, job);
    } else {
        for (int job = 0; job < jobs; ++job)
            direct_simd_tile(a, b, c, n, col_tiles, job);
    }
}
#endif

static void scalar_all(const float* a, const float* b, float* c,
                       int n, int workers)
{
#pragma omp parallel for schedule(static) num_threads(workers) if(n >= 128)
    for (int i = 0; i < n; ++i) {
        float* ci = c + static_cast<std::size_t>(i) * n;
        for (int k = 0; k < n; ++k) {
            const float aik = a[static_cast<std::size_t>(i) * n + k];
            const float* bk = b + static_cast<std::size_t>(k) * n;
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
                sum += a[static_cast<std::size_t>(i) * n + k] *
                       b[static_cast<std::size_t>(k) * n + j];
            c[static_cast<std::size_t>(i) * n + j] = sum;
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
    std::memset(c, 0, static_cast<std::size_t>(n) * n * sizeof(float));

    int workers = threads;
    if (workers < 1) workers = 1;
    if (workers > 8) workers = 8;

#if defined(__GNUC__) && (defined(__x86_64__) || defined(__i386__))
    if (!cpu_has_avx512_fma()) {
        scalar_all(a, b, c, n, workers);
        return;
    }

    const int full_rows = (n / 8) * 8;
    const int full_cols = (n / 32) * 32;
    const int row_tiles = full_rows / 8;

    if (n < 256) {
        direct_simd(a, b, c, n, full_rows, full_cols, workers, false);
        scalar_edges(a, b, c, n, full_rows, full_cols, workers);
        return;
    }

    const int block_k = 128;
    const int block_n = 128;
    const std::size_t a_panel_count = static_cast<std::size_t>(full_rows) * block_k;
    float* a_panel = static_cast<float*>(std::malloc(a_panel_count * sizeof(float)));
    float* b_panel = static_cast<float*>(
        std::malloc(static_cast<std::size_t>(block_k) * block_n * sizeof(float)));
    if (a_panel == nullptr || b_panel == nullptr) {
        std::free(a_panel);
        std::free(b_panel);
        direct_simd(a, b, c, n, full_rows, full_cols, workers, true);
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
                    float* dst = a_panel + static_cast<std::size_t>(row) * block_k;
                    const float* src = a + static_cast<std::size_t>(row) * n + kb;
                    std::memcpy(dst, src, static_cast<std::size_t>(klen) * sizeof(float));
                }
            }

            for (int jb = 0; jb < full_cols; jb += block_n) {
                const int jlen = std::min(block_n, full_cols - jb);
                const int col_tiles = jlen / 32;

#pragma omp for schedule(static)
                for (int kk = 0; kk < klen; ++kk) {
                    float* dst = b_panel + static_cast<std::size_t>(kk) * block_n;
                    const float* src = b + static_cast<std::size_t>(kb + kk) * n + jb;
                    std::memcpy(dst, src, static_cast<std::size_t>(jlen) * sizeof(float));
                    if (jlen < block_n)
                        std::memset(dst + jlen, 0,
                                    static_cast<std::size_t>(block_n - jlen) * sizeof(float));
                }

                const int jobs = row_tiles * col_tiles;
#pragma omp for schedule(static)
                for (int job = 0; job < jobs; ++job) {
                    const int tile_row = job / col_tiles;
                    const int tile_col = job % col_tiles;
                    const int i = tile_row * 8;
                    const int j = jb + tile_col * 32;
                    const float* ap = a_panel + static_cast<std::size_t>(i) * block_k;
                    const float* bp = b_panel + tile_col * 32;
                    float* cp = c + static_cast<std::size_t>(i) * n + j;
                    kernel8x32(ap, bp, cp, block_k, block_n, n,
                               klen, 32, kb != 0);
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
