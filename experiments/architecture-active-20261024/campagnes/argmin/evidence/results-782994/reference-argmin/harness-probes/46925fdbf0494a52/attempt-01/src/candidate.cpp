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
    __m512i vector_min = _mm512_set1_epi32(INT32_MAX);
    int i = 0;

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
    int pos = 0;
    for (; pos <= full_end - 128; pos += 128) {
        const unsigned int mask0 = static_cast<unsigned int>(
            _mm512_cmpeq_epi32_mask(
                _mm512_loadu_si512(static_cast<const void*>(a + pos)), minimum_vector));
        const unsigned int mask1 = static_cast<unsigned int>(
            _mm512_cmpeq_epi32_mask(
                _mm512_loadu_si512(static_cast<const void*>(a + pos + 16)), minimum_vector));
        const unsigned int mask2 = static_cast<unsigned int>(
            _mm512_cmpeq_epi32_mask(
                _mm512_loadu_si512(static_cast<const void*>(a + pos + 32)), minimum_vector));
        const unsigned int mask3 = static_cast<unsigned int>(
            _mm512_cmpeq_epi32_mask(
                _mm512_loadu_si512(static_cast<const void*>(a + pos + 48)), minimum_vector));
        const unsigned int mask4 = static_cast<unsigned int>(
            _mm512_cmpeq_epi32_mask(
                _mm512_loadu_si512(static_cast<const void*>(a + pos + 64)), minimum_vector));
        const unsigned int mask5 = static_cast<unsigned int>(
            _mm512_cmpeq_epi32_mask(
                _mm512_loadu_si512(static_cast<const void*>(a + pos + 80)), minimum_vector));
        const unsigned int mask6 = static_cast<unsigned int>(
            _mm512_cmpeq_epi32_mask(
                _mm512_loadu_si512(static_cast<const void*>(a + pos + 96)), minimum_vector));
        const unsigned int mask7 = static_cast<unsigned int>(
            _mm512_cmpeq_epi32_mask(
                _mm512_loadu_si512(static_cast<const void*>(a + pos + 112)), minimum_vector));

        if (mask0 != 0) {
            first = pos + __builtin_ctz(mask0);
        } else if (mask1 != 0) {
            first = pos + 16 + __builtin_ctz(mask1);
        } else if (mask2 != 0) {
            first = pos + 32 + __builtin_ctz(mask2);
        } else if (mask3 != 0) {
            first = pos + 48 + __builtin_ctz(mask3);
        } else if (mask4 != 0) {
            first = pos + 64 + __builtin_ctz(mask4);
        } else if (mask5 != 0) {
            first = pos + 80 + __builtin_ctz(mask5);
        } else if (mask6 != 0) {
            first = pos + 96 + __builtin_ctz(mask6);
        } else if (mask7 != 0) {
            first = pos + 112 + __builtin_ctz(mask7);
        }

        if (first != n) {
            break;
        }
    }

    if (first == n) {
        for (; pos < full_end; pos += 16) {
            const __m512i values = _mm512_loadu_si512(static_cast<const void*>(a + pos));
            const unsigned int mask = static_cast<unsigned int>(
                _mm512_cmpeq_epi32_mask(values, minimum_vector));
            if (mask != 0) {
                first = pos + __builtin_ctz(mask);
                break;
            }
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
