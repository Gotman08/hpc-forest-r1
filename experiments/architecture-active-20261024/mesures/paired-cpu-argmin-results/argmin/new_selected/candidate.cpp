#include <cstdint>
#include <immintrin.h>

extern "C" void run(const void* input1, const void* input2, void* output,
                     int n, int parameter, int threads)
{
    (void)input2;
    (void)parameter;
    (void)threads;

    int* result = static_cast<int*>(output);
    if (n <= 0) {
        *result = 0;
        return;
    }

    const int* a = static_cast<const int*>(input1);
    const int vector_end = (n / 16) * 16;

    __m512i min0 = _mm512_set1_epi32(INT32_MAX);
    __m512i min1 = _mm512_set1_epi32(INT32_MAX);
    int i = 0;
    for (; vector_end - i >= 32; i += 32) {
        min0 = _mm512_min_epi32(
            min0, _mm512_loadu_si512(static_cast<const void*>(a + i)));
        min1 = _mm512_min_epi32(
            min1, _mm512_loadu_si512(static_cast<const void*>(a + i + 16)));
    }
    if (i < vector_end) {
        min0 = _mm512_min_epi32(
            min0, _mm512_loadu_si512(static_cast<const void*>(a + i)));
    }

    const __m512i vector_min = _mm512_min_epi32(min0, min1);
    int minimum = _mm512_reduce_min_epi32(vector_min);
    for (int tail = vector_end; tail < n; ++tail) {
        if (a[tail] < minimum) {
            minimum = a[tail];
        }
    }

    const __m512i target = _mm512_set1_epi32(minimum);
    int pos = 0;
    for (; pos <= vector_end - 64; pos += 64) {
        const unsigned int m0 = static_cast<unsigned int>(
            _mm512_cmpeq_epi32_mask(
                _mm512_loadu_si512(static_cast<const void*>(a + pos)), target));
        const unsigned int m1 = static_cast<unsigned int>(
            _mm512_cmpeq_epi32_mask(
                _mm512_loadu_si512(static_cast<const void*>(a + pos + 16)), target));
        const unsigned int m2 = static_cast<unsigned int>(
            _mm512_cmpeq_epi32_mask(
                _mm512_loadu_si512(static_cast<const void*>(a + pos + 32)), target));
        const unsigned int m3 = static_cast<unsigned int>(
            _mm512_cmpeq_epi32_mask(
                _mm512_loadu_si512(static_cast<const void*>(a + pos + 48)), target));

        if (m0 != 0) {
            *result = pos + __builtin_ctz(m0);
            return;
        }
        if (m1 != 0) {
            *result = pos + 16 + __builtin_ctz(m1);
            return;
        }
        if (m2 != 0) {
            *result = pos + 32 + __builtin_ctz(m2);
            return;
        }
        if (m3 != 0) {
            *result = pos + 48 + __builtin_ctz(m3);
            return;
        }
    }

    for (; pos < vector_end; pos += 16) {
        const unsigned int matches = static_cast<unsigned int>(
            _mm512_cmpeq_epi32_mask(
                _mm512_loadu_si512(static_cast<const void*>(a + pos)), target));
        if (matches != 0) {
            *result = pos + __builtin_ctz(matches);
            return;
        }
    }

    for (; pos < n; ++pos) {
        if (a[pos] == minimum) {
            *result = pos;
            return;
        }
    }

    *result = 0;
}
