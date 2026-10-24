#include <algorithm>
#include <cstddef>
#include <omp.h>

#if defined(__GNUC__) && (defined(__x86_64__) || defined(__i386__))
#include <immintrin.h>
#define HAVE_TARGETED_AVX512 1

__attribute__((target("avx512f,fma")))
static void kernel_16x16_avx512(const float* a, int lda,
                                const float* b, int bstride,
                                float* c, int ldc,
                                int kc, int cols, bool accumulate)
{
    const __mmask16 mask = cols == 16
        ? static_cast<__mmask16>(0xffffu)
        : static_cast<__mmask16>((1u << cols) - 1u);
    __m512 x0 = accumulate ? _mm512_maskz_loadu_ps(mask, c + 0 * ldc) : _mm512_setzero_ps();
    __m512 x1 = accumulate ? _mm512_maskz_loadu_ps(mask, c + 1 * ldc) : _mm512_setzero_ps();
    __m512 x2 = accumulate ? _mm512_maskz_loadu_ps(mask, c + 2 * ldc) : _mm512_setzero_ps();
    __m512 x3 = accumulate ? _mm512_maskz_loadu_ps(mask, c + 3 * ldc) : _mm512_setzero_ps();
    __m512 x4 = accumulate ? _mm512_maskz_loadu_ps(mask, c + 4 * ldc) : _mm512_setzero_ps();
    __m512 x5 = accumulate ? _mm512_maskz_loadu_ps(mask, c + 5 * ldc) : _mm512_setzero_ps();
    __m512 x6 = accumulate ? _mm512_maskz_loadu_ps(mask, c + 6 * ldc) : _mm512_setzero_ps();
    __m512 x7 = accumulate ? _mm512_maskz_loadu_ps(mask, c + 7 * ldc) : _mm512_setzero_ps();
    __m512 x8 = accumulate ? _mm512_maskz_loadu_ps(mask, c + 8 * ldc) : _mm512_setzero_ps();
    __m512 x9 = accumulate ? _mm512_maskz_loadu_ps(mask, c + 9 * ldc) : _mm512_setzero_ps();
    __m512 x10 = accumulate ? _mm512_maskz_loadu_ps(mask, c + 10 * ldc) : _mm512_setzero_ps();
    __m512 x11 = accumulate ? _mm512_maskz_loadu_ps(mask, c + 11 * ldc) : _mm512_setzero_ps();
    __m512 x12 = accumulate ? _mm512_maskz_loadu_ps(mask, c + 12 * ldc) : _mm512_setzero_ps();
    __m512 x13 = accumulate ? _mm512_maskz_loadu_ps(mask, c + 13 * ldc) : _mm512_setzero_ps();
    __m512 x14 = accumulate ? _mm512_maskz_loadu_ps(mask, c + 14 * ldc) : _mm512_setzero_ps();
    __m512 x15 = accumulate ? _mm512_maskz_loadu_ps(mask, c + 15 * ldc) : _mm512_setzero_ps();

#define GEMM_STEP(row, acc) acc = _mm512_fmadd_ps(_mm512_set1_ps(a[(std::size_t)(row) * lda + k]), bv, acc)
    for (int k = 0; k < kc; ++k) {
        const __m512 bv = _mm512_maskz_loadu_ps(mask, b + static_cast<std::size_t>(k) * bstride);
        GEMM_STEP(0, x0);
        GEMM_STEP(1, x1);
        GEMM_STEP(2, x2);
        GEMM_STEP(3, x3);
        GEMM_STEP(4, x4);
        GEMM_STEP(5, x5);
        GEMM_STEP(6, x6);
        GEMM_STEP(7, x7);
        GEMM_STEP(8, x8);
        GEMM_STEP(9, x9);
        GEMM_STEP(10, x10);
        GEMM_STEP(11, x11);
        GEMM_STEP(12, x12);
        GEMM_STEP(13, x13);
        GEMM_STEP(14, x14);
        GEMM_STEP(15, x15);
    }
#undef GEMM_STEP

    _mm512_mask_storeu_ps(c + 0 * ldc, mask, x0);
    _mm512_mask_storeu_ps(c + 1 * ldc, mask, x1);
    _mm512_mask_storeu_ps(c + 2 * ldc, mask, x2);
    _mm512_mask_storeu_ps(c + 3 * ldc, mask, x3);
    _mm512_mask_storeu_ps(c + 4 * ldc, mask, x4);
    _mm512_mask_storeu_ps(c + 5 * ldc, mask, x5);
    _mm512_mask_storeu_ps(c + 6 * ldc, mask, x6);
    _mm512_mask_storeu_ps(c + 7 * ldc, mask, x7);
    _mm512_mask_storeu_ps(c + 8 * ldc, mask, x8);
    _mm512_mask_storeu_ps(c + 9 * ldc, mask, x9);
    _mm512_mask_storeu_ps(c + 10 * ldc, mask, x10);
    _mm512_mask_storeu_ps(c + 11 * ldc, mask, x11);
    _mm512_mask_storeu_ps(c + 12 * ldc, mask, x12);
    _mm512_mask_storeu_ps(c + 13 * ldc, mask, x13);
    _mm512_mask_storeu_ps(c + 14 * ldc, mask, x14);
    _mm512_mask_storeu_ps(c + 15 * ldc, mask, x15);
}

static bool avx512_is_available()
{
    __builtin_cpu_init();
    return __builtin_cpu_supports("avx512f") && __builtin_cpu_supports("fma");
}
#endif

static void kernel_scalar(const float* a, int lda,
                          const float* b, int bstride,
                          float* c, int ldc,
                          int kc, int rows, int cols, bool accumulate)
{
    float sums[16][16];
    for (int r = 0; r < rows; ++r) {
        for (int x = 0; x < cols; ++x) {
            sums[r][x] = accumulate ? c[static_cast<std::size_t>(r) * ldc + x] : 0.0f;
        }
    }

    for (int k = 0; k < kc; ++k) {
        const float* brow = b + static_cast<std::size_t>(k) * bstride;
        for (int r = 0; r < rows; ++r) {
            const float av = a[static_cast<std::size_t>(r) * lda + k];
            for (int x = 0; x < cols; ++x) {
                sums[r][x] += av * brow[x];
            }
        }
    }

    for (int r = 0; r < rows; ++r) {
        for (int x = 0; x < cols; ++x) {
            c[static_cast<std::size_t>(r) * ldc + x] = sums[r][x];
        }
    }
}

static void compute_tile(const float* a, int lda,
                         const float* b, int bstride,
                         float* c, int ldc,
                         int kc, int rows, int cols, bool accumulate,
                         bool use_avx512)
{
#if defined(HAVE_TARGETED_AVX512)
    if (use_avx512 && rows == 16) {
        kernel_16x16_avx512(a, lda, b, bstride, c, ldc, kc, cols, accumulate);
        return;
    }
#else
    (void)use_avx512;
#endif
    kernel_scalar(a, lda, b, bstride, c, ldc, kc, rows, cols, accumulate);
}

extern "C" void run(const void* input1, const void* input2, void* output,
                    int n, int parameter, int threads)
{
    (void)parameter;
    if (n <= 0) {
        return;
    }

    const float* a = static_cast<const float*>(input1);
    const float* b = static_cast<const float*>(input2);
    float* c = static_cast<float*>(output);
    const int nt = std::max(1, std::min(threads, 8));
    bool use_avx512 = false;
#if defined(HAVE_TARGETED_AVX512)
    use_avx512 = avx512_is_available();
#endif

    constexpr int MR = 16;
    constexpr int NR = 16;

    // Direct-access tile-shape experiment: retain row-major B access and test
    // whether doubling MR improves reuse with the same 16-column SIMD width.
    #pragma omp parallel for collapse(2) schedule(static) num_threads(nt) if(n >= 128)
    for (int ib = 0; ib < n; ib += MR) {
        for (int j = 0; j < n; j += NR) {
            const int rows = std::min(MR, n - ib);
            const int cols = std::min(NR, n - j);
            compute_tile(a + static_cast<std::size_t>(ib) * n, n,
                         b + j, n,
                         c + static_cast<std::size_t>(ib) * n + j, n,
                         n, rows, cols, false, use_avx512);
        }
    }
}
