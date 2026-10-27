#include <cstddef>
#if defined(__AVX512F__)
#include <immintrin.h>
#endif

extern "C" void run(const void* input1, const void* input2, void* output,
                    int n, int parameter, int threads)
{
    (void)parameter;
    if (n <= 0) return;

    const float* A = static_cast<const float*>(input1);
    const float* B = static_cast<const float*>(input2);
    float* C = static_cast<float*>(output);
    const std::size_t stride = static_cast<std::size_t>(n);
    const int row_blocks = n / 16 + (n % 16 != 0);
    const int requested = threads > 0 ? threads : 1;
    const int team_size = requested < row_blocks ? requested : row_blocks;

    // Each statically scheduled iteration owns a disjoint 16-row tile.
    #pragma omp parallel for schedule(static) num_threads(team_size) if(team_size > 1)
    for (int block = 0; block < row_blocks; ++block) {
        const int i = block * 16;
        if (n - i < 16) {
            // Scalar bottom-row tail; overwrite every output element.
            for (int row = i; row < n; ++row) {
                const float* a = A + static_cast<std::size_t>(row) * stride;
                float* c = C + static_cast<std::size_t>(row) * stride;
                for (int j = 0; j < n; ++j) {
                    float sum = 0.0f;
                    for (int k = 0; k < n; ++k)
                        sum += a[k] * B[static_cast<std::size_t>(k) * stride + j];
                    c[j] = sum;
                }
            }
            continue;
        }

        int j = 0;
#if defined(__AVX512F__)
        for (; j <= n - 16; j += 16) {
            __m512 c0 = _mm512_setzero_ps();
            __m512 c1 = _mm512_setzero_ps();
            __m512 c2 = _mm512_setzero_ps();
            __m512 c3 = _mm512_setzero_ps();
            __m512 c4 = _mm512_setzero_ps();
            __m512 c5 = _mm512_setzero_ps();
            __m512 c6 = _mm512_setzero_ps();
            __m512 c7 = _mm512_setzero_ps();
            __m512 c8 = _mm512_setzero_ps();
            __m512 c9 = _mm512_setzero_ps();
            __m512 c10 = _mm512_setzero_ps();
            __m512 c11 = _mm512_setzero_ps();
            __m512 c12 = _mm512_setzero_ps();
            __m512 c13 = _mm512_setzero_ps();
            __m512 c14 = _mm512_setzero_ps();
            __m512 c15 = _mm512_setzero_ps();

            const float* a = A + static_cast<std::size_t>(i) * stride;
            for (int k = 0; k < n; ++k) {
                const __m512 b = _mm512_loadu_ps(
                    B + static_cast<std::size_t>(k) * stride + j);
#define UPDATE_ROW(R, ACC) ACC = _mm512_fmadd_ps(_mm512_set1_ps(a[static_cast<std::size_t>(R) * stride + k]), b, ACC)
                UPDATE_ROW(0, c0);
                UPDATE_ROW(1, c1);
                UPDATE_ROW(2, c2);
                UPDATE_ROW(3, c3);
                UPDATE_ROW(4, c4);
                UPDATE_ROW(5, c5);
                UPDATE_ROW(6, c6);
                UPDATE_ROW(7, c7);
                UPDATE_ROW(8, c8);
                UPDATE_ROW(9, c9);
                UPDATE_ROW(10, c10);
                UPDATE_ROW(11, c11);
                UPDATE_ROW(12, c12);
                UPDATE_ROW(13, c13);
                UPDATE_ROW(14, c14);
                UPDATE_ROW(15, c15);
#undef UPDATE_ROW
            }

            float* c = C + static_cast<std::size_t>(i) * stride + j;
            _mm512_storeu_ps(c, c0);
            _mm512_storeu_ps(c + stride, c1);
            _mm512_storeu_ps(c + 2 * stride, c2);
            _mm512_storeu_ps(c + 3 * stride, c3);
            _mm512_storeu_ps(c + 4 * stride, c4);
            _mm512_storeu_ps(c + 5 * stride, c5);
            _mm512_storeu_ps(c + 6 * stride, c6);
            _mm512_storeu_ps(c + 7 * stride, c7);
            _mm512_storeu_ps(c + 8 * stride, c8);
            _mm512_storeu_ps(c + 9 * stride, c9);
            _mm512_storeu_ps(c + 10 * stride, c10);
            _mm512_storeu_ps(c + 11 * stride, c11);
            _mm512_storeu_ps(c + 12 * stride, c12);
            _mm512_storeu_ps(c + 13 * stride, c13);
            _mm512_storeu_ps(c + 14 * stride, c14);
            _mm512_storeu_ps(c + 15 * stride, c15);
        }
#else
        for (; j <= n - 16; j += 16) {
            float accum[16][16] = {};
            for (int k = 0; k < n; ++k) {
                const float* b = B + static_cast<std::size_t>(k) * stride + j;
                for (int row = 0; row < 16; ++row) {
                    const float a = A[static_cast<std::size_t>(i + row) * stride + k];
                    #pragma omp simd
                    for (int col = 0; col < 16; ++col)
                        accum[row][col] += a * b[col];
                }
            }
            for (int row = 0; row < 16; ++row) {
                float* c = C + (static_cast<std::size_t>(i + row) * stride) + j;
                for (int col = 0; col < 16; ++col)
                    c[col] = accum[row][col];
            }
        }
#endif

        // Scalar right-column tail for this full row tile.
        for (; j < n; ++j) {
            float sums[16] = {};
            for (int k = 0; k < n; ++k) {
                const float b = B[static_cast<std::size_t>(k) * stride + j];
                for (int row = 0; row < 16; ++row)
                    sums[row] += A[static_cast<std::size_t>(i + row) * stride + k] * b;
            }
            for (int row = 0; row < 16; ++row)
                C[static_cast<std::size_t>(i + row) * stride + j] = sums[row];
        }
    }
}
