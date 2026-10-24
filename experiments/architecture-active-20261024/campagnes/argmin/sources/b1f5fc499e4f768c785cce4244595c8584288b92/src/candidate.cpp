#include <immintrin.h>
#include <climits>

extern "C" __attribute__((target("avx512f")))
void run(const void* input1, const void* input2, void* output, int n, int parameter, int threads)
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
    const __m512i lane_offsets = _mm512_setr_epi32(
        0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15);
    __m512i lane_min = _mm512_set1_epi32(INT_MAX);
    __m512i lane_index = _mm512_set1_epi32(INT_MAX);

    int base = 0;
    int remaining = n;
    while (remaining >= 16) {
        const __m512i values = _mm512_loadu_si512(static_cast<const void*>(a + base));
        const __m512i indices = _mm512_add_epi32(_mm512_set1_epi32(base), lane_offsets);
        const __mmask16 lower = _mm512_cmp_epi32_mask(values, lane_min, _MM_CMPINT_LT);
        const __mmask16 equal = _mm512_cmp_epi32_mask(values, lane_min, _MM_CMPINT_EQ);
        const __mmask16 earlier = _mm512_cmp_epi32_mask(indices, lane_index, _MM_CMPINT_LT);
        const __mmask16 improve = lower | (equal & earlier);
        lane_min = _mm512_mask_mov_epi32(lane_min, improve, values);
        lane_index = _mm512_mask_mov_epi32(lane_index, improve, indices);
        base += 16;
        remaining -= 16;
    }

    if (remaining > 0) {
        const __mmask16 active = static_cast<__mmask16>((1u << remaining) - 1u);
        const __m512i values = _mm512_maskz_loadu_epi32(
            active, static_cast<const void*>(a + base));
        const __m512i indices = _mm512_add_epi32(_mm512_set1_epi32(base), lane_offsets);
        const __mmask16 lower = _mm512_cmp_epi32_mask(values, lane_min, _MM_CMPINT_LT);
        const __mmask16 equal = _mm512_cmp_epi32_mask(values, lane_min, _MM_CMPINT_EQ);
        const __mmask16 earlier = _mm512_cmp_epi32_mask(indices, lane_index, _MM_CMPINT_LT);
        const __mmask16 improve = (lower | (equal & earlier)) & active;
        lane_min = _mm512_mask_mov_epi32(lane_min, improve, values);
        lane_index = _mm512_mask_mov_epi32(lane_index, improve, indices);
    }

    alignas(64) int lane_values[16];
    alignas(64) int lane_indices[16];
    _mm512_storeu_si512(static_cast<void*>(lane_values), lane_min);
    _mm512_storeu_si512(static_cast<void*>(lane_indices), lane_index);

    int best_value = lane_values[0];
    int best_index = lane_indices[0];
    for (int lane = 1; lane < 16; ++lane) {
        if (lane_values[lane] < best_value ||
            (lane_values[lane] == best_value && lane_indices[lane] < best_index)) {
            best_value = lane_values[lane];
            best_index = lane_indices[lane];
        }
    }

    *result = best_index;
}
