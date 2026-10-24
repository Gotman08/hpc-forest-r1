#include <cstddef>
#include <immintrin.h>
#include <omp.h>

static void scalar_tile(const float* a, const float* b, float* c, int n,
                        int row0, int col0, int rows, int cols) {
    const std::size_t ns = static_cast<std::size_t>(n);
    for (int r = row0; r < row0 + rows; ++r) {
        const std::size_t row = static_cast<std::size_t>(r) * ns;
        for (int col = col0; col < col0 + cols; ++col) {
            float sum = 0.0f;
            const std::size_t cc = static_cast<std::size_t>(col);
            for (int k = 0; k < n; ++k) {
                sum += a[row + static_cast<std::size_t>(k)] *
                       b[static_cast<std::size_t>(k) * ns + cc];
            }
            c[row + cc] = sum;
        }
    }
}

__attribute__((target("avx512f,fma")))
static void kernel_8x32_direct(const float* a, const float* b, float* c,
                               int n, int row0, int col0) {
    const std::size_t ns = static_cast<std::size_t>(n);
    const std::size_t cs = static_cast<std::size_t>(col0);
    const float* a0 = a + static_cast<std::size_t>(row0 + 0) * ns;
    const float* a1 = a + static_cast<std::size_t>(row0 + 1) * ns;
    const float* a2 = a + static_cast<std::size_t>(row0 + 2) * ns;
    const float* a3 = a + static_cast<std::size_t>(row0 + 3) * ns;
    const float* a4 = a + static_cast<std::size_t>(row0 + 4) * ns;
    const float* a5 = a + static_cast<std::size_t>(row0 + 5) * ns;
    const float* a6 = a + static_cast<std::size_t>(row0 + 6) * ns;
    const float* a7 = a + static_cast<std::size_t>(row0 + 7) * ns;

    __m512 v00 = _mm512_setzero_ps(), v01 = _mm512_setzero_ps();
    __m512 v10 = _mm512_setzero_ps(), v11 = _mm512_setzero_ps();
    __m512 v20 = _mm512_setzero_ps(), v21 = _mm512_setzero_ps();
    __m512 v30 = _mm512_setzero_ps(), v31 = _mm512_setzero_ps();
    __m512 v40 = _mm512_setzero_ps(), v41 = _mm512_setzero_ps();
    __m512 v50 = _mm512_setzero_ps(), v51 = _mm512_setzero_ps();
    __m512 v60 = _mm512_setzero_ps(), v61 = _mm512_setzero_ps();
    __m512 v70 = _mm512_setzero_ps(), v71 = _mm512_setzero_ps();

    for (int k = 0; k < n; ++k) {
        const float* bk = b + static_cast<std::size_t>(k) * ns + cs;
        const __m512 b0 = _mm512_loadu_ps(bk);
        const __m512 b1 = _mm512_loadu_ps(bk + 16);
        const __m512 x0 = _mm512_set1_ps(a0[k]);
        const __m512 x1 = _mm512_set1_ps(a1[k]);
        const __m512 x2 = _mm512_set1_ps(a2[k]);
        const __m512 x3 = _mm512_set1_ps(a3[k]);
        const __m512 x4 = _mm512_set1_ps(a4[k]);
        const __m512 x5 = _mm512_set1_ps(a5[k]);
        const __m512 x6 = _mm512_set1_ps(a6[k]);
        const __m512 x7 = _mm512_set1_ps(a7[k]);
        v00 = _mm512_fmadd_ps(x0, b0, v00); v01 = _mm512_fmadd_ps(x0, b1, v01);
        v10 = _mm512_fmadd_ps(x1, b0, v10); v11 = _mm512_fmadd_ps(x1, b1, v11);
        v20 = _mm512_fmadd_ps(x2, b0, v20); v21 = _mm512_fmadd_ps(x2, b1, v21);
        v30 = _mm512_fmadd_ps(x3, b0, v30); v31 = _mm512_fmadd_ps(x3, b1, v31);
        v40 = _mm512_fmadd_ps(x4, b0, v40); v41 = _mm512_fmadd_ps(x4, b1, v41);
        v50 = _mm512_fmadd_ps(x5, b0, v50); v51 = _mm512_fmadd_ps(x5, b1, v51);
        v60 = _mm512_fmadd_ps(x6, b0, v60); v61 = _mm512_fmadd_ps(x6, b1, v61);
        v70 = _mm512_fmadd_ps(x7, b0, v70); v71 = _mm512_fmadd_ps(x7, b1, v71);
    }

    float* c0 = c + static_cast<std::size_t>(row0 + 0) * ns + cs;
    float* c1 = c + static_cast<std::size_t>(row0 + 1) * ns + cs;
    float* c2 = c + static_cast<std::size_t>(row0 + 2) * ns + cs;
    float* c3 = c + static_cast<std::size_t>(row0 + 3) * ns + cs;
    float* c4 = c + static_cast<std::size_t>(row0 + 4) * ns + cs;
    float* c5 = c + static_cast<std::size_t>(row0 + 5) * ns + cs;
    float* c6 = c + static_cast<std::size_t>(row0 + 6) * ns + cs;
    float* c7 = c + static_cast<std::size_t>(row0 + 7) * ns + cs;
    _mm512_storeu_ps(c0, v00); _mm512_storeu_ps(c0 + 16, v01);
    _mm512_storeu_ps(c1, v10); _mm512_storeu_ps(c1 + 16, v11);
    _mm512_storeu_ps(c2, v20); _mm512_storeu_ps(c2 + 16, v21);
    _mm512_storeu_ps(c3, v30); _mm512_storeu_ps(c3 + 16, v31);
    _mm512_storeu_ps(c4, v40); _mm512_storeu_ps(c4 + 16, v41);
    _mm512_storeu_ps(c5, v50); _mm512_storeu_ps(c5 + 16, v51);
    _mm512_storeu_ps(c6, v60); _mm512_storeu_ps(c6 + 16, v61);
    _mm512_storeu_ps(c7, v70); _mm512_storeu_ps(c7 + 16, v71);
}

extern "C" void run(const void* input1, const void* input2, void* output,
                    int n, int parameter, int threads) {
    (void)parameter;
    if (n <= 0) return;

    const float* a = static_cast<const float*>(input1);
    const float* b = static_cast<const float*>(input2);
    float* c = static_cast<float*>(output);
    const long long row_tiles = static_cast<long long>(n / 8 + (n % 8 != 0));
    const long long col_tiles = static_cast<long long>(n / 32 + (n % 32 != 0));

    int nt = threads > 0 ? threads : 1;
    if (nt > 8) nt = 8;
    if (static_cast<long long>(nt) > row_tiles) {
        nt = static_cast<int>(row_tiles);
    }

#pragma omp parallel num_threads(nt)
    {
        const long long team = static_cast<long long>(omp_get_num_threads());
        const long long tid = static_cast<long long>(omp_get_thread_num());
        const long long ti_begin = row_tiles * tid / team;
        const long long ti_end = row_tiles * (tid + 1) / team;

        for (long long ti = ti_begin; ti < ti_end; ++ti) {
            for (long long pj = 0; pj < col_tiles; ++pj) {
                const int row0 = static_cast<int>(ti * 8);
                const int col0 = static_cast<int>(pj * 32);
                const int rows = n - row0 < 8 ? n - row0 : 8;
                const int cols = n - col0 < 32 ? n - col0 : 32;
                if (rows == 8 && cols == 32) {
                    kernel_8x32_direct(a, b, c, n, row0, col0);
                } else {
                    scalar_tile(a, b, c, n, row0, col0, rows, cols);
                }
            }
        }
    }
}
