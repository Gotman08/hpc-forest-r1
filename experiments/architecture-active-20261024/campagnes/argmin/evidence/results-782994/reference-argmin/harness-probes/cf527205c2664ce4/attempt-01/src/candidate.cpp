#include <immintrin.h>

extern "C" void run(const void* input1, const void*, void* output, int n, int, int)
{
    const int* a = static_cast<const int*>(input1);
    int* result = static_cast<int*>(output);

    if (n <= 0) {
        *result = 0;
        return;
    }

    if (n < 16) {
        int best = 0;
        for (int i = 1; i < n; ++i) {
            if (a[i] < a[best]) {
                best = i;
            }
        }
        *result = best;
        return;
    }

    __m512i lane_min = _mm512_loadu_si512(static_cast<const void*>(a));
    int lane_index[16];
    for (int lane = 0; lane < 16; ++lane) {
        lane_index[lane] = lane;
    }

    int i = 16;
    for (; i <= n - 16; i += 16) {
        const __m512i values = _mm512_loadu_si512(static_cast<const void*>(a + i));
        const __mmask16 changed = _mm512_cmp_epi32_mask(values, lane_min, _MM_CMPINT_LT);
        lane_min = _mm512_mask_mov_epi32(lane_min, changed, values);

        unsigned int pending = static_cast<unsigned int>(changed);
        while (pending != 0) {
            const unsigned int lane = static_cast<unsigned int>(__builtin_ctz(pending));
            lane_index[lane] = i + static_cast<int>(lane);
            pending &= pending - 1;
        }
    }

    int best_value = _mm512_reduce_min_epi32(lane_min);
    const __mmask16 minimum_lanes = _mm512_cmpeq_epi32_mask(
        lane_min, _mm512_set1_epi32(best_value));
    unsigned int pending = static_cast<unsigned int>(minimum_lanes);
    int best_index = n;
    while (pending != 0) {
        const unsigned int lane = static_cast<unsigned int>(__builtin_ctz(pending));
        if (lane_index[lane] < best_index) {
            best_index = lane_index[lane];
        }
        pending &= pending - 1;
    }

    for (; i < n; ++i) {
        if (a[i] < best_value) {
            best_value = a[i];
            best_index = i;
        }
    }

    *result = best_index;
}