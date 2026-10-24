#include <algorithm>
#include <cstddef>
#include <cstring>
#include <vector>
#include <omp.h>

#if defined(__GNUC__) && (defined(__x86_64__) || defined(__i386__))
#include <immintrin.h>
#define HAVE_TARGETED_AVX512 1

__attribute__((target("avx512f,fma")))
static void kernel_8x32_avx512(const float* a, int lda,
                               const float* b, int bstride,
                               float* c, int ldc,
                               int kc, int cols, bool accumulate)
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
        const std::size_t b_offset = static_cast<std::size_t>(k) * bstride;
        const __m512 b_low = _mm512_maskz_loadu_ps(low_mask, b + b_offset);
        __m512 b_high = _mm512_setzero_ps();
        if (has_high) {
            b_high = _mm512_maskz_loadu_ps(high_mask, b + b_offset + 16);
        }

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
    float sums[8][32];
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
        kernel_8x32_avx512(a, lda, b, bstride, c, ldc, kc, cols, accumulate);
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
    constexpr int NR = 32;
    constexpr int KC = 128;
    constexpr int NC = 128;

    if (n < 2 * NC) {
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

    // Retain the selected parent's B-only panel loop so the NR change is
    // measured with the same packing, allocation, and output ownership.
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
