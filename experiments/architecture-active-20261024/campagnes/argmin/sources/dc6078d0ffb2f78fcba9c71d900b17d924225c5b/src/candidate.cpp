#include <cstdint>
#include <cstring>
#include <cmath>
#include <algorithm>
#include <omp.h>
#include <immintrin.h>

extern "C" void run(const void* input1, const void* input2, void* output, int n, int parameter, int threads)
{
    const int* a = static_cast<const int*>(input1);
    int* result = static_cast<int*>(output);
    if (n <= 0) {
        *result = 0;
        return;
    }

    const int vector_end = (n / 16) * 16;
    __m512i vector_min = _mm512_set1_epi32(INT32_MAX);
    for (int i = 0; i < vector_end; i += 16) {
        const __m512i values = _mm512_loadu_si512(static_cast<const void*>(a + i));
        vector_min = _mm512_min_epi32(vector_min, values);
    }

    int minimum = _mm512_reduce_min_epi32(vector_min);
    for (int i = vector_end; i < n; ++i) {
        if (a[i] < minimum) {
            minimum = a[i];
        }
    }

    const __m512i target = _mm512_set1_epi32(minimum);
    int i = 0;
    for (; i <= vector_end - 64; i += 64) {
        const __mmask16 m0 = _mm512_cmpeq_epi32_mask(_mm512_loadu_si512(static_cast<const void*>(a + i)), target);
        const __mmask16 m1 = _mm512_cmpeq_epi32_mask(_mm512_loadu_si512(static_cast<const void*>(a + i + 16)), target);
        const __mmask16 m2 = _mm512_cmpeq_epi32_mask(_mm512_loadu_si512(static_cast<const void*>(a + i + 32)), target);
        const __mmask16 m3 = _mm512_cmpeq_epi32_mask(_mm512_loadu_si512(static_cast<const void*>(a + i + 48)), target);

        if ((m0 | m1 | m2 | m3) != 0) {
            if (m0 != 0) {
                *result = i + __builtin_ctz(static_cast<unsigned int>(m0));
                return;
            }
            if (m1 != 0) {
                *result = i + 16 + __builtin_ctz(static_cast<unsigned int>(m1));
                return;
            }
            if (m2 != 0) {
                *result = i + 32 + __builtin_ctz(static_cast<unsigned int>(m2));
                return;
            }
            *result = i + 48 + __builtin_ctz(static_cast<unsigned int>(m3));
            return;
        }
    }

    for (; i < vector_end; i += 16) {
        const __mmask16 matches = _mm512_cmpeq_epi32_mask(
            _mm512_loadu_si512(static_cast<const void*>(a + i)), target);
        if (matches != 0) {
            *result = i + __builtin_ctz(static_cast<unsigned int>(matches));
            return;
        }
    }

    for (; i < n; ++i) {
        if (a[i] == minimum) {
            *result = i;
            return;
        }
    }

    *result = 0;
}
