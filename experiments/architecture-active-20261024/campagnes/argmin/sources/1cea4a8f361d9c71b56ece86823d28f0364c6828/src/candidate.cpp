#include <immintrin.h>

extern "C" __attribute__((target("avx512f")))
void run(const void* input1, const void* input2, void* output, int n, int parameter, int threads)
{
    (void)input2;
    (void)parameter;
    (void)threads;

    const int* a = static_cast<const int*>(input1);
    int* result = static_cast<int*>(output);

    if (n < 16) {
        int best_index = 0;
        if (n > 0) {
            int best_value = a[0];
            for (int i = 1; i < n; ++i) {
                if (a[i] < best_value || (a[i] == best_value && i < best_index)) {
                    best_value = a[i];
                    best_index = i;
                }
            }
        }
        *result = best_index;
        return;
    }

    __m512i lane_min = _mm512_loadu_si512(static_cast<const void*>(a));
    __m512i lane_indices = _mm512_setr_epi32(0, 1, 2, 3, 4, 5, 6, 7,
                                             8, 9, 10, 11, 12, 13, 14, 15);
    __m512i current_indices = lane_indices;
    const __m512i stride = _mm512_set1_epi32(16);

    for (int base = 16; base <= n - 16; base += 16) {
        current_indices = _mm512_add_epi32(current_indices, stride);
        const __m512i values = _mm512_loadu_si512(static_cast<const void*>(a + base));
        const __mmask16 improve = _mm512_cmp_epi32_mask(values, lane_min, _MM_CMPINT_LT);
        lane_min = _mm512_mask_mov_epi32(lane_min, improve, values);
        lane_indices = _mm512_mask_mov_epi32(lane_indices, improve, current_indices);
    }

    alignas(64) int lane_values[16];
    alignas(64) int lane_first_indices[16];
    _mm512_storeu_si512(static_cast<void*>(lane_values), lane_min);
    _mm512_storeu_si512(static_cast<void*>(lane_first_indices), lane_indices);

    int best_value = lane_values[0];
    int best_index = lane_first_indices[0];
    for (int lane = 1; lane < 16; ++lane) {
        if (lane_values[lane] < best_value ||
            (lane_values[lane] == best_value && lane_first_indices[lane] < best_index)) {
            best_value = lane_values[lane];
            best_index = lane_first_indices[lane];
        }
    }

    const int tail_start = (n / 16) * 16;
    for (int i = tail_start; i < n; ++i) {
        if (a[i] < best_value || (a[i] == best_value && i < best_index)) {
            best_value = a[i];
            best_index = i;
        }
    }

    *result = best_index;
}
