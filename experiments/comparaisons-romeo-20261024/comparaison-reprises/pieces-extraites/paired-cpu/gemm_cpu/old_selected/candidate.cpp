#include <cstddef>
#include <omp.h>

#if defined(__x86_64__) || defined(__i386__)
#include <immintrin.h>

static void simd_4x16_row_block(const float* a, const float* b, float* c,
                                int n, int row) __attribute__((target("avx2,fma")));

static void simd_4x16_row_block(const float* a, const float* b, float* c,
                                int n, int row) {
    const std::size_t nn = static_cast<std::size_t>(n);
    const int vector_end = (n / 16) * 16;

    for (int col = 0; col < vector_end; col += 16) {
        __m256 acc00 = _mm256_setzero_ps();
        __m256 acc01 = _mm256_setzero_ps();
        __m256 acc10 = _mm256_setzero_ps();
        __m256 acc11 = _mm256_setzero_ps();
        __m256 acc20 = _mm256_setzero_ps();
        __m256 acc21 = _mm256_setzero_ps();
        __m256 acc30 = _mm256_setzero_ps();
        __m256 acc31 = _mm256_setzero_ps();

        for (int k = 0; k < n; ++k) {
            const std::size_t b_index = static_cast<std::size_t>(k) * nn + col;
            const __m256 b0 = _mm256_loadu_ps(b + b_index);
            const __m256 b1 = _mm256_loadu_ps(b + b_index + 8);
            const __m256 a0 = _mm256_set1_ps(a[static_cast<std::size_t>(row) * nn + k]);
            const __m256 a1 = _mm256_set1_ps(a[static_cast<std::size_t>(row + 1) * nn + k]);
            const __m256 a2 = _mm256_set1_ps(a[static_cast<std::size_t>(row + 2) * nn + k]);
            const __m256 a3 = _mm256_set1_ps(a[static_cast<std::size_t>(row + 3) * nn + k]);

            acc00 = _mm256_fmadd_ps(a0, b0, acc00);
            acc01 = _mm256_fmadd_ps(a0, b1, acc01);
            acc10 = _mm256_fmadd_ps(a1, b0, acc10);
            acc11 = _mm256_fmadd_ps(a1, b1, acc11);
            acc20 = _mm256_fmadd_ps(a2, b0, acc20);
            acc21 = _mm256_fmadd_ps(a2, b1, acc21);
            acc30 = _mm256_fmadd_ps(a3, b0, acc30);
            acc31 = _mm256_fmadd_ps(a3, b1, acc31);
        }

        const std::size_t c0 = static_cast<std::size_t>(row) * nn + col;
        const std::size_t c1 = static_cast<std::size_t>(row + 1) * nn + col;
        const std::size_t c2 = static_cast<std::size_t>(row + 2) * nn + col;
        const std::size_t c3 = static_cast<std::size_t>(row + 3) * nn + col;
        _mm256_storeu_ps(c + c0, acc00);
        _mm256_storeu_ps(c + c0 + 8, acc01);
        _mm256_storeu_ps(c + c1, acc10);
        _mm256_storeu_ps(c + c1 + 8, acc11);
        _mm256_storeu_ps(c + c2, acc20);
        _mm256_storeu_ps(c + c2 + 8, acc21);
        _mm256_storeu_ps(c + c3, acc30);
        _mm256_storeu_ps(c + c3 + 8, acc31);
    }

    for (int col = vector_end; col < n; ++col) {
        for (int rr = 0; rr < 4; ++rr) {
            float sum = 0.0f;
            const std::size_t a_index = static_cast<std::size_t>(row + rr) * nn;
            for (int k = 0; k < n; ++k) {
                sum += a[a_index + k] * b[static_cast<std::size_t>(k) * nn + col];
            }
            c[a_index + col] = sum;
        }
    }
}
#endif

extern "C" void run(const void* input1, const void* input2, void* output,
                    int n, int parameter, int threads) {
    (void)parameter;
    if (n <= 0) {
        return;
    }

    const float* a = static_cast<const float*>(input1);
    const float* b = static_cast<const float*>(input2);
    float* c = static_cast<float*>(output);
    const std::size_t nn = static_cast<std::size_t>(n);
    const int thread_count = threads > 0 ? threads : 1;

#if defined(__x86_64__) || defined(__i386__)
    __builtin_cpu_init();
    if (__builtin_cpu_supports("avx2") && __builtin_cpu_supports("fma")) {
        const int row_blocks = n / 4;
        #pragma omp parallel for schedule(static) num_threads(thread_count)
        for (int block = 0; block < row_blocks; ++block) {
            simd_4x16_row_block(a, b, c, n, block * 4);
        }

        for (int row = row_blocks * 4; row < n; ++row) {
            const std::size_t row_index = static_cast<std::size_t>(row) * nn;
            for (int col = 0; col < n; ++col) {
                float sum = 0.0f;
                for (int k = 0; k < n; ++k) {
                    sum += a[row_index + k] * b[static_cast<std::size_t>(k) * nn + col];
                }
                c[row_index + col] = sum;
            }
        }
        return;
    }
#endif

    #pragma omp parallel for schedule(static) num_threads(thread_count)
    for (int row = 0; row < n; ++row) {
        const std::size_t row_index = static_cast<std::size_t>(row) * nn;
        for (int col = 0; col < n; ++col) {
            float sum = 0.0f;
            for (int k = 0; k < n; ++k) {
                sum += a[row_index + k] * b[static_cast<std::size_t>(k) * nn + col];
            }
            c[row_index + col] = sum;
        }
    }
}
