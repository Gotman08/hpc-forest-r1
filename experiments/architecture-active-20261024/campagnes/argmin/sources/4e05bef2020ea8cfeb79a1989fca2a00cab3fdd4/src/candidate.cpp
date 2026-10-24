#include <cstdint>
#include <climits>
#include <immintrin.h>

extern "C" __attribute__((target("avx512f")))
void run(const void* input1, const void* input2, void* output,
         int n, int parameter, int threads)
{
    (void)input2;
    (void)parameter;
    (void)threads;

    if (n <= 0) {
        *static_cast<int*>(output) = 0;
        return;
    }

    const int32_t* a = static_cast<const int32_t*>(input1);
    const int full_end = n - n % 16;
    const int vector_end = full_end - full_end % 64;
    __m512i min0 = _mm512_set1_epi32(INT32_MAX);
    __m512i min1 = _mm512_set1_epi32(INT32_MAX);
    __m512i min2 = _mm512_set1_epi32(INT32_MAX);
    __m512i min3 = _mm512_set1_epi32(INT32_MAX);
    int i = 0;

    for (; i < vector_end; i += 64) {
        const __m512i values0 = _mm512_loadu_si512(static_cast<const void*>(a + i));
        const __m512i values1 = _mm512_loadu_si512(static_cast<const void*>(a + i + 16));
        const __m512i values2 = _mm512_loadu_si512(static_cast<const void*>(a + i + 32));
        const __m512i values3 = _mm512_loadu_si512(static_cast<const void*>(a + i + 48));
        min0 = _mm512_min_epi32(min0, values0);
        min1 = _mm512_min_epi32(min1, values1);
        min2 = _mm512_min_epi32(min2, values2);
        min3 = _mm512_min_epi32(min3, values3);
    }

    __m512i vector_min = _mm512_min_epi32(
        _mm512_min_epi32(min0, min1), _mm512_min_epi32(min2, min3));
    for (; i < full_end; i += 16) {
        const __m512i values = _mm512_loadu_si512(static_cast<const void*>(a + i));
        vector_min = _mm512_min_epi32(vector_min, values);
    }

    alignas(64) int32_t lanes[16];
    _mm512_store_si512(static_cast<void*>(lanes), vector_min);

    int32_t global_min = INT32_MAX;
    for (int lane = 0; lane < 16; ++lane) {
        if (lanes[lane] < global_min) {
            global_min = lanes[lane];
        }
    }
    for (; i < n; ++i) {
        if (a[i] < global_min) {
            global_min = a[i];
        }
    }

    const __m512i minimum_vector = _mm512_set1_epi32(global_min);
    int first = n;
    for (int pos = 0; pos < full_end; pos += 16) {
        const __m512i values = _mm512_loadu_si512(static_cast<const void*>(a + pos));
        const unsigned int mask = static_cast<unsigned int>(
            _mm512_cmpeq_epi32_mask(values, minimum_vector));
        if (mask != 0) {
            first = pos + __builtin_ctz(mask);
            break;
        }
    }

    if (first == n) {
        for (int pos = full_end; pos < n; ++pos) {
            if (a[pos] == global_min) {
                first = pos;
                break;
            }
        }
    }

    *static_cast<int*>(output) = first;
}
