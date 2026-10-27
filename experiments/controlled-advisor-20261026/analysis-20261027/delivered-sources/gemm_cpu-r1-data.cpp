// Confirmation identity marker only; executable code below is unchanged.
#include <algorithm>
#include <cstddef>
#include <cstring>

namespace {

constexpr int kRowBlock = 32;

int block_count(int n) {
    return n > 0 ? 1 + (n - 1) / kRowBlock : 0;
}

static void mm_scalar_row(const float* A, const float* B, float* C, int n, int r) {
    const std::size_t stride = static_cast<std::size_t>(n);
    const std::size_t row = static_cast<std::size_t>(r) * stride;
    float* out = C + row;
    for (int k = 0; k < n; ++k) {
        const float a = A[row + static_cast<std::size_t>(k)];
        const std::size_t b_row = static_cast<std::size_t>(k) * stride;
        for (int c = 0; c < n; ++c) {
            out[c] += a * B[b_row + static_cast<std::size_t>(c)];
        }
    }
}

static void mm_scalar_rows(const float* A, const float* B, float* C,
                           int n, int row_begin, int row_end) {
    for (int r = row_begin; r < row_end; ++r) {
        mm_scalar_row(A, B, C, n, r);
    }
}

#if (defined(__GNUC__) || defined(__clang__)) && (defined(__x86_64__) || defined(__i386__))
#include <immintrin.h>

__attribute__((target("avx512f,fma")))
static void mm_avx512_rows(const float* A, const float* B, float* C,
                           int n, int row_begin, int row_end) {
    const std::size_t stride = static_cast<std::size_t>(n);
    int r = row_begin;
    for (; r <= row_end - 4; r += 4) {
        int c = 0;
        for (; c <= n - 16; c += 16) {
            __m512 acc0 = _mm512_setzero_ps();
            __m512 acc1 = _mm512_setzero_ps();
            __m512 acc2 = _mm512_setzero_ps();
            __m512 acc3 = _mm512_setzero_ps();
            const std::size_t arow = static_cast<std::size_t>(r) * stride;
            for (int k = 0; k < n; ++k) {
                const std::size_t kk = static_cast<std::size_t>(k);
                const __m512 b = _mm512_loadu_ps(B + kk * stride + static_cast<std::size_t>(c));
                acc0 = _mm512_fmadd_ps(_mm512_set1_ps(A[arow + kk]), b, acc0);
                acc1 = _mm512_fmadd_ps(_mm512_set1_ps(A[arow + stride + kk]), b, acc1);
                acc2 = _mm512_fmadd_ps(_mm512_set1_ps(A[arow + 2 * stride + kk]), b, acc2);
                acc3 = _mm512_fmadd_ps(_mm512_set1_ps(A[arow + 3 * stride + kk]), b, acc3);
            }
            const std::size_t crow = static_cast<std::size_t>(r) * stride + static_cast<std::size_t>(c);
            _mm512_storeu_ps(C + crow, acc0);
            _mm512_storeu_ps(C + crow + stride, acc1);
            _mm512_storeu_ps(C + crow + 2 * stride, acc2);
            _mm512_storeu_ps(C + crow + 3 * stride, acc3);
        }
        for (; c < n; ++c) {
            float s0 = 0.0f, s1 = 0.0f, s2 = 0.0f, s3 = 0.0f;
            const std::size_t arow = static_cast<std::size_t>(r) * stride;
            for (int k = 0; k < n; ++k) {
                const std::size_t kk = static_cast<std::size_t>(k);
                const float b = B[kk * stride + static_cast<std::size_t>(c)];
                s0 += A[arow + kk] * b;
                s1 += A[arow + stride + kk] * b;
                s2 += A[arow + 2 * stride + kk] * b;
                s3 += A[arow + 3 * stride + kk] * b;
            }
            const std::size_t crow = static_cast<std::size_t>(r) * stride + static_cast<std::size_t>(c);
            C[crow] = s0;
            C[crow + stride] = s1;
            C[crow + 2 * stride] = s2;
            C[crow + 3 * stride] = s3;
        }
    }
    for (; r < row_end; ++r) {
        mm_scalar_row(A, B, C, n, r);
    }
}
#endif

static void multiply_rows(const float* A, const float* B, float* C, int n,
                          int row_begin, int row_end, bool use_avx512) {
#if (defined(__GNUC__) || defined(__clang__)) && (defined(__x86_64__) || defined(__i386__))
    if (use_avx512) {
        mm_avx512_rows(A, B, C, n, row_begin, row_end);
        return;
    }
#else
    (void)use_avx512;
#endif
    mm_scalar_rows(A, B, C, n, row_begin, row_end);
}

}  // namespace

extern "C" void run(const void* input1, const void* input2, void* output,
                    int n, int parameter, int threads) {
    (void)parameter;
    if (n <= 0) return;

    const float* A = static_cast<const float*>(input1);
    const float* B = static_cast<const float*>(input2);
    float* C = static_cast<float*>(output);
    const std::size_t elements = static_cast<std::size_t>(n) * static_cast<std::size_t>(n);
    std::memset(C, 0, elements * sizeof(float));

    bool use_avx512 = false;
#if (defined(__GNUC__) || defined(__clang__)) && (defined(__x86_64__) || defined(__i386__))
    if (n >= 16) {
        __builtin_cpu_init();
        use_avx512 = __builtin_cpu_supports("avx512f") && __builtin_cpu_supports("fma");
    }
#endif

    const int row_blocks = block_count(n);
    int workers = 1;
    if (threads > 1 && row_blocks > 1) {
        workers = std::min(threads, row_blocks);
    }

    #pragma omp parallel for schedule(static) num_threads(workers) if(workers > 1)
    for (int ib = 0; ib < row_blocks; ++ib) {
        const int row_begin = ib * kRowBlock;
        const int row_end = row_begin + std::min(kRowBlock, n - row_begin);
        multiply_rows(A, B, C, n, row_begin, row_end, use_avx512);
    }
}
