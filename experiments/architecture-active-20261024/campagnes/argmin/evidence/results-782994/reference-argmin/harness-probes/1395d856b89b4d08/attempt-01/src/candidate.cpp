#include <immintrin.h>

extern "C" __attribute__((target("avx512f")))
void run(const void* input1, const void*, void* output, int n, int, int)
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

    // Seed from real input so INT32_MAX is a valid lane minimum.
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

        // Only lanes with a strictly smaller value need a new absolute index.
        unsigned int pending = static_cast<unsigned int>(changed);
        while (pending != 0) {
            const unsigned int lane = static_cast<unsigned int>(__builtin_ctz(pending));
            lane_index[lane] = i + static_cast<int>(lane);
            pending &= pending - 1;
        }
    }

    int lane_values[16];
    _mm512_storeu_si512(static_cast<void*>(lane_values), lane_min);
    int best_index = lane_index[0];
    int best_value = lane_values[0];
    for (int lane = 1; lane < 16; ++lane) {
        if (lane_values[lane] < best_value ||
            (lane_values[lane] == best_value && lane_index[lane] < best_index)) {
            best_value = lane_values[lane];
            best_index = lane_index[lane];
        }
    }

    for (; i < n; ++i) {
        if (a[i] < best_value || (a[i] == best_value && i < best_index)) {
            best_value = a[i];
            best_index = i;
        }
    }

    *result = best_index;
}
