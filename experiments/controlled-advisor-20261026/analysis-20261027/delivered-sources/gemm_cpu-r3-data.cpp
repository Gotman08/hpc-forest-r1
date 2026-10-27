#include <cstddef>
#include <cstring>
#include <omp.h>

#if (defined(__GNUC__) || defined(__clang__)) && (defined(__i386__) || defined(__x86_64__))
#include <immintrin.h>
#define HAVE_AVX2_FMA_DISPATCH 1
#define AVX2_FMA_TARGET __attribute__((target("avx2,fma")))
#define AVX512_FMA_TARGET __attribute__((target("avx512f,fma")))
#else
#define HAVE_AVX2_FMA_DISPATCH 0
#define AVX2_FMA_TARGET
#define AVX512_FMA_TARGET
#endif

static void multiply_tile_scalar(const float* A, const float* B, float* C,
                                 std::size_t N, std::size_t first_row,
                                 std::size_t row_count)
{
    for (std::size_t r = 0; r < row_count; ++r) {
        const std::size_t i = first_row + r;
        for (std::size_t j = 0; j < N; ++j) {
            float sum = 0.0f;
            for (std::size_t k = 0; k < N; ++k)
                sum += A[i * N + k] * B[k * N + j];
            C[i * N + j] = sum;
        }
    }
}

#if HAVE_AVX2_FMA_DISPATCH
static AVX512_FMA_TARGET void multiply_tile8_avx512_fma(
    const float* A, const float* B, float* C, std::size_t N,
    std::size_t first_row)
{
    std::size_t j = 0;
    for (; j + 32 <= N; j += 32) {
        __m512 c00 = _mm512_setzero_ps();
        __m512 c01 = _mm512_setzero_ps();
        __m512 c10 = _mm512_setzero_ps();
        __m512 c11 = _mm512_setzero_ps();
        __m512 c20 = _mm512_setzero_ps();
        __m512 c21 = _mm512_setzero_ps();
        __m512 c30 = _mm512_setzero_ps();
        __m512 c31 = _mm512_setzero_ps();
        __m512 c40 = _mm512_setzero_ps();
        __m512 c41 = _mm512_setzero_ps();
        __m512 c50 = _mm512_setzero_ps();
        __m512 c51 = _mm512_setzero_ps();
        __m512 c60 = _mm512_setzero_ps();
        __m512 c61 = _mm512_setzero_ps();
        __m512 c70 = _mm512_setzero_ps();
        __m512 c71 = _mm512_setzero_ps();

        for (std::size_t k = 0; k < N; ++k) {
            const __m512 b0 = _mm512_loadu_ps(B + k * N + j);
            const __m512 b1 = _mm512_loadu_ps(B + k * N + j + 16);
            const __m512 a0 = _mm512_set1_ps(A[(first_row + 0) * N + k]);
            const __m512 a1 = _mm512_set1_ps(A[(first_row + 1) * N + k]);
            const __m512 a2 = _mm512_set1_ps(A[(first_row + 2) * N + k]);
            const __m512 a3 = _mm512_set1_ps(A[(first_row + 3) * N + k]);
            const __m512 a4 = _mm512_set1_ps(A[(first_row + 4) * N + k]);
            const __m512 a5 = _mm512_set1_ps(A[(first_row + 5) * N + k]);
            const __m512 a6 = _mm512_set1_ps(A[(first_row + 6) * N + k]);
            const __m512 a7 = _mm512_set1_ps(A[(first_row + 7) * N + k]);

            c00 = _mm512_fmadd_ps(a0, b0, c00);
            c01 = _mm512_fmadd_ps(a0, b1, c01);
            c10 = _mm512_fmadd_ps(a1, b0, c10);
            c11 = _mm512_fmadd_ps(a1, b1, c11);
            c20 = _mm512_fmadd_ps(a2, b0, c20);
            c21 = _mm512_fmadd_ps(a2, b1, c21);
            c30 = _mm512_fmadd_ps(a3, b0, c30);
            c31 = _mm512_fmadd_ps(a3, b1, c31);
            c40 = _mm512_fmadd_ps(a4, b0, c40);
            c41 = _mm512_fmadd_ps(a4, b1, c41);
            c50 = _mm512_fmadd_ps(a5, b0, c50);
            c51 = _mm512_fmadd_ps(a5, b1, c51);
            c60 = _mm512_fmadd_ps(a6, b0, c60);
            c61 = _mm512_fmadd_ps(a6, b1, c61);
            c70 = _mm512_fmadd_ps(a7, b0, c70);
            c71 = _mm512_fmadd_ps(a7, b1, c71);
        }

        _mm512_storeu_ps(C + (first_row + 0) * N + j, c00);
        _mm512_storeu_ps(C + (first_row + 0) * N + j + 16, c01);
        _mm512_storeu_ps(C + (first_row + 1) * N + j, c10);
        _mm512_storeu_ps(C + (first_row + 1) * N + j + 16, c11);
        _mm512_storeu_ps(C + (first_row + 2) * N + j, c20);
        _mm512_storeu_ps(C + (first_row + 2) * N + j + 16, c21);
        _mm512_storeu_ps(C + (first_row + 3) * N + j, c30);
        _mm512_storeu_ps(C + (first_row + 3) * N + j + 16, c31);
        _mm512_storeu_ps(C + (first_row + 4) * N + j, c40);
        _mm512_storeu_ps(C + (first_row + 4) * N + j + 16, c41);
        _mm512_storeu_ps(C + (first_row + 5) * N + j, c50);
        _mm512_storeu_ps(C + (first_row + 5) * N + j + 16, c51);
        _mm512_storeu_ps(C + (first_row + 6) * N + j, c60);
        _mm512_storeu_ps(C + (first_row + 6) * N + j + 16, c61);
        _mm512_storeu_ps(C + (first_row + 7) * N + j, c70);
        _mm512_storeu_ps(C + (first_row + 7) * N + j + 16, c71);
    }

    for (; j + 16 <= N; j += 16) {
        __m512 c0 = _mm512_setzero_ps();
        __m512 c1 = _mm512_setzero_ps();
        __m512 c2 = _mm512_setzero_ps();
        __m512 c3 = _mm512_setzero_ps();
        __m512 c4 = _mm512_setzero_ps();
        __m512 c5 = _mm512_setzero_ps();
        __m512 c6 = _mm512_setzero_ps();
        __m512 c7 = _mm512_setzero_ps();

        for (std::size_t k = 0; k < N; ++k) {
            const __m512 b = _mm512_loadu_ps(B + k * N + j);
            const __m512 a0 = _mm512_set1_ps(A[(first_row + 0) * N + k]);
            const __m512 a1 = _mm512_set1_ps(A[(first_row + 1) * N + k]);
            const __m512 a2 = _mm512_set1_ps(A[(first_row + 2) * N + k]);
            const __m512 a3 = _mm512_set1_ps(A[(first_row + 3) * N + k]);
            const __m512 a4 = _mm512_set1_ps(A[(first_row + 4) * N + k]);
            const __m512 a5 = _mm512_set1_ps(A[(first_row + 5) * N + k]);
            const __m512 a6 = _mm512_set1_ps(A[(first_row + 6) * N + k]);
            const __m512 a7 = _mm512_set1_ps(A[(first_row + 7) * N + k]);

            c0 = _mm512_fmadd_ps(a0, b, c0);
            c1 = _mm512_fmadd_ps(a1, b, c1);
            c2 = _mm512_fmadd_ps(a2, b, c2);
            c3 = _mm512_fmadd_ps(a3, b, c3);
            c4 = _mm512_fmadd_ps(a4, b, c4);
            c5 = _mm512_fmadd_ps(a5, b, c5);
            c6 = _mm512_fmadd_ps(a6, b, c6);
            c7 = _mm512_fmadd_ps(a7, b, c7);
        }

        _mm512_storeu_ps(C + (first_row + 0) * N + j, c0);
        _mm512_storeu_ps(C + (first_row + 1) * N + j, c1);
        _mm512_storeu_ps(C + (first_row + 2) * N + j, c2);
        _mm512_storeu_ps(C + (first_row + 3) * N + j, c3);
        _mm512_storeu_ps(C + (first_row + 4) * N + j, c4);
        _mm512_storeu_ps(C + (first_row + 5) * N + j, c5);
        _mm512_storeu_ps(C + (first_row + 6) * N + j, c6);
        _mm512_storeu_ps(C + (first_row + 7) * N + j, c7);
    }

    for (; j < N; ++j) {
        for (std::size_t r = 0; r < 8; ++r) {
            const std::size_t i = first_row + r;
            float sum = 0.0f;
            for (std::size_t k = 0; k < N; ++k)
                sum += A[i * N + k] * B[k * N + j];
            C[i * N + j] = sum;
        }
    }
}

static AVX512_FMA_TARGET void multiply_tile_avx512_fma(
    const float* A, const float* B, float* C, std::size_t N,
    std::size_t first_row)
{
    std::size_t j = 0;
    for (; j + 16 <= N; j += 16) {
        __m512 c0 = _mm512_setzero_ps();
        __m512 c1 = _mm512_setzero_ps();
        __m512 c2 = _mm512_setzero_ps();
        __m512 c3 = _mm512_setzero_ps();

        for (std::size_t k = 0; k < N; ++k) {
            const __m512 b = _mm512_loadu_ps(B + k * N + j);
            const __m512 a0 = _mm512_set1_ps(A[(first_row + 0) * N + k]);
            const __m512 a1 = _mm512_set1_ps(A[(first_row + 1) * N + k]);
            const __m512 a2 = _mm512_set1_ps(A[(first_row + 2) * N + k]);
            const __m512 a3 = _mm512_set1_ps(A[(first_row + 3) * N + k]);

            c0 = _mm512_fmadd_ps(a0, b, c0);
            c1 = _mm512_fmadd_ps(a1, b, c1);
            c2 = _mm512_fmadd_ps(a2, b, c2);
            c3 = _mm512_fmadd_ps(a3, b, c3);
        }

        _mm512_storeu_ps(C + (first_row + 0) * N + j, c0);
        _mm512_storeu_ps(C + (first_row + 1) * N + j, c1);
        _mm512_storeu_ps(C + (first_row + 2) * N + j, c2);
        _mm512_storeu_ps(C + (first_row + 3) * N + j, c3);
    }

    for (; j < N; ++j) {
        for (std::size_t r = 0; r < 4; ++r) {
            const std::size_t i = first_row + r;
            float sum = 0.0f;
            for (std::size_t k = 0; k < N; ++k)
                sum += A[i * N + k] * B[k * N + j];
            C[i * N + j] = sum;
        }
    }
}

static AVX2_FMA_TARGET void multiply_tile_avx2_fma(
    const float* A, const float* B, float* C, std::size_t N,
    std::size_t first_row)
{
    std::size_t j = 0;
    for (; j + 16 <= N; j += 16) {
        __m256 c00 = _mm256_setzero_ps();
        __m256 c01 = _mm256_setzero_ps();
        __m256 c10 = _mm256_setzero_ps();
        __m256 c11 = _mm256_setzero_ps();
        __m256 c20 = _mm256_setzero_ps();
        __m256 c21 = _mm256_setzero_ps();
        __m256 c30 = _mm256_setzero_ps();
        __m256 c31 = _mm256_setzero_ps();

        for (std::size_t k = 0; k < N; ++k) {
            const __m256 b0 = _mm256_loadu_ps(B + k * N + j);
            const __m256 b1 = _mm256_loadu_ps(B + k * N + j + 8);
            const __m256 a0 = _mm256_set1_ps(A[(first_row + 0) * N + k]);
            const __m256 a1 = _mm256_set1_ps(A[(first_row + 1) * N + k]);
            const __m256 a2 = _mm256_set1_ps(A[(first_row + 2) * N + k]);
            const __m256 a3 = _mm256_set1_ps(A[(first_row + 3) * N + k]);

            c00 = _mm256_fmadd_ps(a0, b0, c00);
            c01 = _mm256_fmadd_ps(a0, b1, c01);
            c10 = _mm256_fmadd_ps(a1, b0, c10);
            c11 = _mm256_fmadd_ps(a1, b1, c11);
            c20 = _mm256_fmadd_ps(a2, b0, c20);
            c21 = _mm256_fmadd_ps(a2, b1, c21);
            c30 = _mm256_fmadd_ps(a3, b0, c30);
            c31 = _mm256_fmadd_ps(a3, b1, c31);
        }

        _mm256_storeu_ps(C + (first_row + 0) * N + j, c00);
        _mm256_storeu_ps(C + (first_row + 0) * N + j + 8, c01);
        _mm256_storeu_ps(C + (first_row + 1) * N + j, c10);
        _mm256_storeu_ps(C + (first_row + 1) * N + j + 8, c11);
        _mm256_storeu_ps(C + (first_row + 2) * N + j, c20);
        _mm256_storeu_ps(C + (first_row + 2) * N + j + 8, c21);
        _mm256_storeu_ps(C + (first_row + 3) * N + j, c30);
        _mm256_storeu_ps(C + (first_row + 3) * N + j + 8, c31);
    }

    for (; j < N; ++j) {
        for (std::size_t r = 0; r < 4; ++r) {
            const std::size_t i = first_row + r;
            float sum = 0.0f;
            for (std::size_t k = 0; k < N; ++k)
                sum += A[i * N + k] * B[k * N + j];
            C[i * N + j] = sum;
        }
    }
}
#endif

extern "C" void run(const void* input1, const void* input2, void* output,
                    int n, int parameter, int threads)
{
    (void)parameter;
    if (n <= 0)
        return;

    const std::size_t N = static_cast<std::size_t>(n);
    const float* A = static_cast<const float*>(input1);
    const float* B = static_cast<const float*>(input2);
    float* C = static_cast<float*>(output);

    const int row_tiles = n / 4 + ((n % 4) != 0 ? 1 : 0);
    int team = threads;
    if (team < 1) team = 1;
    if (team > row_tiles) team = row_tiles;

#if HAVE_AVX2_FMA_DISPATCH
    bool use_avx512_fma = false;
    bool use_avx2_fma = false;
    if (N >= 16) {
        __builtin_cpu_init();
        use_avx512_fma = __builtin_cpu_supports("avx512f") &&
                         __builtin_cpu_supports("fma");
        use_avx2_fma = __builtin_cpu_supports("avx2") &&
                       __builtin_cpu_supports("fma");
    }

    if (use_avx512_fma) {
        const int row_tiles8 = n / 8 + ((n % 8) != 0 ? 1 : 0);
        int team8 = threads;
        if (team8 < 1) team8 = 1;
        if (team8 > row_tiles8) team8 = row_tiles8;

        #pragma omp parallel for schedule(static) num_threads(team8) if(team8 > 1)
        for (int tile = 0; tile < row_tiles8; ++tile) {
            const std::size_t first_row = static_cast<std::size_t>(tile) * 8;
            const std::size_t remaining_rows = N - first_row;
            if (remaining_rows >= 8)
                multiply_tile8_avx512_fma(A, B, C, N, first_row);
            else if (remaining_rows >= 4)
                multiply_tile_avx512_fma(A, B, C, N, first_row);
            else
                multiply_tile_scalar(A, B, C, N, first_row, remaining_rows);
        }
        return;
    }

    if (use_avx2_fma) {
        #pragma omp parallel for schedule(static) num_threads(team) if(team > 1)
        for (int tile = 0; tile < row_tiles; ++tile) {
            const std::size_t first_row = static_cast<std::size_t>(tile) * 4;
            if (N - first_row >= 4)
                multiply_tile_avx2_fma(A, B, C, N, first_row);
            else
                multiply_tile_scalar(A, B, C, N, first_row, N - first_row);
        }
        return;
    }
#endif

    #pragma omp parallel for schedule(static) num_threads(team) if(team > 1)
    for (int tile = 0; tile < row_tiles; ++tile) {
        const std::size_t first_row = static_cast<std::size_t>(tile) * 4;
        const std::size_t row_count = N - first_row < 4 ? N - first_row : 4;
        multiply_tile_scalar(A, B, C, N, first_row, row_count);
    }
}
