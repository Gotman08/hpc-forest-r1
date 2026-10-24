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
    __m512i min0 = _mm512_set1_epi32(INT32_MAX);
    __m512i min1 = _mm512_set1_epi32(INT32_MAX);
    __m512i min2 = _mm512_set1_epi32(INT32_MAX);
    __m512i min3 = _mm512_set1_epi32(INT32_MAX);
    int i = 0;

    for (; i <= full_end - 64; i += 64) {
        min0 = _mm512_min_epi32(
            min0, _mm512_loadu_si512(static_cast<const void*>(a + i)));
        min1 = _mm512_min_epi32(
            min1, _mm512_loadu_si512(static_cast<const void*>(a + i + 16)));
        min2 = _mm512_min_epi32(
            min2, _mm512_loadu_si512(static_cast<const void*>(a + i + 32)));
        min3 = _mm512_min_epi32(
            min3, _mm512_loadu_si512(static_cast<const void*>(a + i + 48)));
    }

    __m512i vector_min = _mm512_min_epi32(
        _mm512_min_epi32(min0, min1), _mm512_min_epi32(min2, min3));
    for (; i < full_end; i += 16) {
        vector_min = _mm512_min_epi32(
            vector_min,
            _mm512_loadu_si512(static_cast<const void*>(a + i)));
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
    int pos = 0;
    for (; pos <= full_end - 64; pos += 64) {
        const unsigned int mask0 = static_cast<unsigned int>(
            _mm512_cmpeq_epi32_mask(
                _mm512_loadu_si512(static_cast<const void*>(a + pos)),
                minimum_vector));
        const unsigned int mask1 = static_cast<unsigned int>(
            _mm512_cmpeq_epi32_mask(
                _mm512_loadu_si512(static_cast<const void*>(a + pos + 16)),
                minimum_vector));
        const unsigned int mask2 = static_cast<unsigned int>(
            _mm512_cmpeq_epi32_mask(
                _mm512_loadu_si512(static_cast<const void*>(a + pos + 32)),
                minimum_vector));
        const unsigned int mask3 = static_cast<unsigned int>(
            _mm512_cmpeq_epi32_mask(
                _mm512_loadu_si512(static_cast<const void*>(a + pos + 48)),
                minimum_vector));

        if (mask0 != 0) {
            first = pos + __builtin_ctz(mask0);
            break;
        }
        if (mask1 != 0) {
            first = pos + 16 + __builtin_ctz(mask1);
            break;
        }
        if (mask2 != 0) {
            first = pos + 32 + __builtin_ctz(mask2);
            break;
        }
        if (mask3 != 0) {
            first = pos + 48 + __builtin_ctz(mask3);
            break;
        }
    }

    for (; first == n && pos < full_end; pos += 16) {
        const unsigned int mask = static_cast<unsigned int>(
            _mm512_cmpeq_epi32_mask(
                _mm512_loadu_si512(static_cast<const void*>(a + pos)),
                minimum_vector));
        if (mask != 0) {
            first = pos + __builtin_ctz(mask);
        }
    }

    if (first == n) {
        for (int tail = full_end; tail < n; ++tail) {
            if (a[tail] == global_min) {
                first = tail;
                break;
            }
        }
    }

    *static_cast<int*>(output) = first;
}
