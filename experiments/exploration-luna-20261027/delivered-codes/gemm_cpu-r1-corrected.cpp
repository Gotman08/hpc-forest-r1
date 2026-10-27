#include <cstddef>
#include <omp.h>

#if (defined(__GNUC__) || defined(__clang__)) && (defined(__x86_64__) || defined(__i386__))
#include <immintrin.h>

static __attribute__((target("avx"), always_inline)) inline void add_k_avx(
    __m256& c0, __m256& c1, __m256& c2, __m256& c3,
    __m256& c4, __m256& c5, __m256& c6, __m256& c7,
    const float* a0, const float* a1, const float* a2, const float* a3,
    const float* a4, const float* a5, const float* a6, const float* a7,
    const float* B, std::size_t n, std::size_t j, std::size_t k) {
    const __m256 b = _mm256_loadu_ps(B + k * n + j);
    c0 = _mm256_add_ps(c0, _mm256_mul_ps(_mm256_set1_ps(a0[k]), b));
    c1 = _mm256_add_ps(c1, _mm256_mul_ps(_mm256_set1_ps(a1[k]), b));
    c2 = _mm256_add_ps(c2, _mm256_mul_ps(_mm256_set1_ps(a2[k]), b));
    c3 = _mm256_add_ps(c3, _mm256_mul_ps(_mm256_set1_ps(a3[k]), b));
    c4 = _mm256_add_ps(c4, _mm256_mul_ps(_mm256_set1_ps(a4[k]), b));
    c5 = _mm256_add_ps(c5, _mm256_mul_ps(_mm256_set1_ps(a5[k]), b));
    c6 = _mm256_add_ps(c6, _mm256_mul_ps(_mm256_set1_ps(a6[k]), b));
    c7 = _mm256_add_ps(c7, _mm256_mul_ps(_mm256_set1_ps(a7[k]), b));
}

static __attribute__((target("avx"))) void tile8x8_avx(
    const float* A, const float* B, float* C, std::size_t n,
    std::size_t i, std::size_t j) {
    __m256 c0 = _mm256_setzero_ps();
    __m256 c1 = _mm256_setzero_ps();
    __m256 c2 = _mm256_setzero_ps();
    __m256 c3 = _mm256_setzero_ps();
    __m256 c4 = _mm256_setzero_ps();
    __m256 c5 = _mm256_setzero_ps();
    __m256 c6 = _mm256_setzero_ps();
    __m256 c7 = _mm256_setzero_ps();

    const float* a0 = A + (i + 0) * n;
    const float* a1 = A + (i + 1) * n;
    const float* a2 = A + (i + 2) * n;
    const float* a3 = A + (i + 3) * n;
    const float* a4 = A + (i + 4) * n;
    const float* a5 = A + (i + 5) * n;
    const float* a6 = A + (i + 6) * n;
    const float* a7 = A + (i + 7) * n;

    std::size_t k = 0;
    for (; k + 4 <= n; k += 4) {
        add_k_avx(c0, c1, c2, c3, c4, c5, c6, c7,
                  a0, a1, a2, a3, a4, a5, a6, a7, B, n, j, k + 0);
        add_k_avx(c0, c1, c2, c3, c4, c5, c6, c7,
                  a0, a1, a2, a3, a4, a5, a6, a7, B, n, j, k + 1);
        add_k_avx(c0, c1, c2, c3, c4, c5, c6, c7,
                  a0, a1, a2, a3, a4, a5, a6, a7, B, n, j, k + 2);
        add_k_avx(c0, c1, c2, c3, c4, c5, c6, c7,
                  a0, a1, a2, a3, a4, a5, a6, a7, B, n, j, k + 3);
    }
    for (; k < n; ++k) {
        add_k_avx(c0, c1, c2, c3, c4, c5, c6, c7,
                  a0, a1, a2, a3, a4, a5, a6, a7, B, n, j, k);
    }

    _mm256_storeu_ps(C + (i + 0) * n + j, c0);
    _mm256_storeu_ps(C + (i + 1) * n + j, c1);
    _mm256_storeu_ps(C + (i + 2) * n + j, c2);
    _mm256_storeu_ps(C + (i + 3) * n + j, c3);
    _mm256_storeu_ps(C + (i + 4) * n + j, c4);
    _mm256_storeu_ps(C + (i + 5) * n + j, c5);
    _mm256_storeu_ps(C + (i + 6) * n + j, c6);
    _mm256_storeu_ps(C + (i + 7) * n + j, c7);
}
#endif

constexpr int ROW_TILE = 16;

static inline void multiply_row_tile(const float* A, const float* B, float* C,
                                     int n, int tile, bool avx_available) {
    const std::size_t dimension = static_cast<std::size_t>(n);
    const std::size_t row_begin = static_cast<std::size_t>(tile) * ROW_TILE;
    const std::size_t row_count =
        dimension - row_begin < ROW_TILE ? dimension - row_begin : ROW_TILE;
    const std::size_t row_end = row_begin + row_count;

    for (std::size_t i = row_begin; i < row_end; ) {
        const std::size_t rows = row_end - i < 8 ? row_end - i : 8;
        for (std::size_t j = 0; j < dimension; ) {
            const std::size_t cols = dimension - j < 8 ? dimension - j : 8;
#if (defined(__GNUC__) || defined(__clang__)) && (defined(__x86_64__) || defined(__i386__))
            if (avx_available && rows == 8 && cols == 8) {
                tile8x8_avx(A, B, C, dimension, i, j);
                j += cols;
                continue;
            }
#endif
            for (std::size_t r = 0; r < rows; ++r) {
                for (std::size_t c = 0; c < cols; ++c) {
                    float sum = 0.0f;
                    for (std::size_t k = 0; k < dimension; ++k)
                        sum += A[(i + r) * dimension + k] *
                               B[k * dimension + j + c];
                    C[(i + r) * dimension + j + c] = sum;
                }
            }
            j += cols;
        }
        i += rows;
    }
}

extern "C" void run(const void* input1, const void* input2, void* output,
                    int n, int, int threads) {
    if (n <= 0) return;

    const float* A = static_cast<const float*>(input1);
    const float* B = static_cast<const float*>(input2);
    float* C = static_cast<float*>(output);
    const int row_tiles = n / ROW_TILE + (n % ROW_TILE != 0);

    bool avx_available = false;
#if (defined(__GNUC__) || defined(__clang__)) && (defined(__x86_64__) || defined(__i386__))
    __builtin_cpu_init();
    avx_available = __builtin_cpu_supports("avx");
#endif

    int team = 1;
    if (threads > 1 && row_tiles > 1 && !omp_in_parallel())
        team = threads < row_tiles ? threads : row_tiles;

    if (team == 1) {
        for (int tile = 0; tile < row_tiles; ++tile)
            multiply_row_tile(A, B, C, n, tile, avx_available);
    } else {
        #pragma omp parallel for schedule(static) num_threads(team)
        for (int tile = 0; tile < row_tiles; ++tile)
            multiply_row_tile(A, B, C, n, tile, avx_available);
    }
}
