#include <algorithm>
#include <cstddef>
#include <cstring>
#include <vector>
#include <omp.h>

#if defined(__GNUC__) && (defined(__x86_64__) || defined(__i386__))
#include <immintrin.h>
#define HAVE_TARGETED_AVX512 1

__attribute__((target("avx512f,fma")))
static void kernel_8x16_avx512(const float* a, int lda,
                               const float* b, int bstride,
                               float* c, int ldc,
                               int kc, int cols, bool accumulate)
{
    const __mmask16 mask = static_cast<__mmask16>((1u << cols) - 1u);
    __m512 x0 = accumulate ? _mm512_maskz_loadu_ps(mask, c + 0 * ldc) : _mm512_setzero_ps();
    __m512 x1 = accumulate ? _mm512_maskz_loadu_ps(mask, c + 1 * ldc) : _mm512_setzero_ps();
    __m512 x2 = accumulate ? _mm512_maskz_loadu_ps(mask, c + 2 * ldc) : _mm512_setzero_ps();
    __m512 x3 = accumulate ? _mm512_maskz_loadu_ps(mask, c + 3 * ldc) : _mm512_setzero_ps();
    __m512 x4 = accumulate ? _mm512_maskz_loadu_ps(mask, c + 4 * ldc) : _mm512_setzero_ps();
    __m512 x5 = accumulate ? _mm512_maskz_loadu_ps(mask, c + 5 * ldc) : _mm512_setzero_ps();
    __m512 x6 = accumulate ? _mm512_maskz_loadu_ps(mask, c + 6 * ldc) : _mm512_setzero_ps();
    __m512 x7 = accumulate ? _mm512_maskz_loadu_ps(mask, c + 7 * ldc) : _mm512_setzero_ps();

    for (int k = 0; k < kc; ++k) {
        const __m512 bv = _mm512_maskz_loadu_ps(mask, b + static_cast<std::size_t>(k) * bstride);
        x0 = _mm512_fmadd_ps(_mm512_set1_ps(a[k]), bv, x0);
        x1 = _mm512_fmadd_ps(_mm512_set1_ps(a[lda + k]), bv, x1);
        x2 = _mm512_fmadd_ps(_mm512_set1_ps(a[2 * lda + k]), bv, x2);
        x3 = _mm512_fmadd_ps(_mm512_set1_ps(a[3 * lda + k]), bv, x3);
        x4 = _mm512_fmadd_ps(_mm512_set1_ps(a[4 * lda + k]), bv, x4);
        x5 = _mm512_fmadd_ps(_mm512_set1_ps(a[5 * lda + k]), bv, x5);
        x6 = _mm512_fmadd_ps(_mm512_set1_ps(a[6 * lda + k]), bv, x6);
        x7 = _mm512_fmadd_ps(_mm512_set1_ps(a[7 * lda + k]), bv, x7);
    }

    _mm512_mask_storeu_ps(c + 0 * ldc, mask, x0);
    _mm512_mask_storeu_ps(c + 1 * ldc, mask, x1);
    _mm512_mask_storeu_ps(c + 2 * ldc, mask, x2);
    _mm512_mask_storeu_ps(c + 3 * ldc, mask, x3);
    _mm512_mask_storeu_ps(c + 4 * ldc, mask, x4);
    _mm512_mask_storeu_ps(c + 5 * ldc, mask, x5);
    _mm512_mask_storeu_ps(c + 6 * ldc, mask, x6);
    _mm512_mask_storeu_ps(c + 7 * ldc, mask, x7);
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
    float sums[8][16];
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
    if (use_avx512 && rows == 8) {
        kernel_8x16_avx512(a, lda, b, bstride, c, ldc, kc, cols, accumulate);
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

    constexpr int MR = 8;
    constexpr int NR = 16;
    constexpr int KC = 128;
    constexpr int NC = 256;
    constexpr int DIRECT_ACCESS_LIMIT = 256;

    if (n < DIRECT_ACCESS_LIMIT) {
        #pragma omp parallel for collapse(2) schedule(static) num_threads(nt)
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
        return;
    }

    // B-only panels retain the microkernel's contiguous column vectors.
    // The per-call scratch allocation and copies are part of run's cost.
    std::vector<float> packed(static_cast<std::size_t>(KC) * NC);
    #pragma omp parallel num_threads(nt) shared(packed)
    {
        for (int jc = 0; jc < n; jc += NC) {
            const int nc = std::min(NC, n - jc);
            for (int pc = 0; pc < n; pc += KC) {
                const int kc = std::min(KC, n - pc);
                #pragma omp single
                {
                    for (int k = 0; k < kc; ++k) {
                        std::memcpy(packed.data() + static_cast<std::size_t>(k) * nc,
                                    b + static_cast<std::size_t>(pc + k) * n + jc,
                                    static_cast<std::size_t>(nc) * sizeof(float));
                    }
                }
                #pragma omp for schedule(static)
                for (int ib = 0; ib < n; ib += MR) {
                    const int rows = std::min(MR, n - ib);
                    for (int j = 0; j < nc; j += NR) {
                        const int cols = std::min(NR, nc - j);
                        compute_tile(a + static_cast<std::size_t>(ib) * n + pc, n,
                                     packed.data() + j, nc,
                                     c + static_cast<std::size_t>(ib) * n + jc + j, n,
                                     kc, rows, cols, pc != 0, use_avx512);
                    }
                }
            }
        }
    }
}
