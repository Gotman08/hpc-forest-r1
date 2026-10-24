#include <climits>
#include <immintrin.h>

extern "C" void run(const void* input1, const void* input2, void* output, int n,
                     int parameter, int threads)
{
    (void)input2;
    (void)parameter;
    (void)threads;

    const int* a = static_cast<const int*>(input1);
    int* result = static_cast<int*>(output);

    if (n <= 0) {
        *result = 0;
        return;
    }

    if (n < 16) {
        int best_index = 0;
        for (int i = 1; i < n; ++i) {
            if (a[i] < a[best_index]) {
                best_index = i;
            }
        }
        *result = best_index;
        return;
    }

    const int vector_end = n - n % 16;
    const __m512i lanes = _mm512_set_epi32(15, 14, 13, 12, 11, 10, 9, 8,
                                           7, 6, 5, 4, 3, 2, 1, 0);

    __m512i min_a = _mm512_loadu_si512(static_cast<const void*>(a));
    __m512i index_a = lanes;
    __m512i min_b = _mm512_set1_epi32(INT_MAX);
    __m512i index_b = _mm512_set1_epi32(INT_MAX);

    if (vector_end >= 32) {
        min_b = _mm512_loadu_si512(static_cast<const void*>(a + 16));
        index_b = _mm512_add_epi32(lanes, _mm512_set1_epi32(16));
    }

    int next = 32;
    for (; vector_end - next >= 32; next += 32) {
        const __m512i cur_a =
            _mm512_loadu_si512(static_cast<const void*>(a + next));
        const __m512i cur_index_a =
            _mm512_add_epi32(lanes, _mm512_set1_epi32(next));
        const __mmask16 better_a =
            _mm512_cmp_epi32_mask(cur_a, min_a, _MM_CMPINT_LT);
        min_a = _mm512_mask_mov_epi32(min_a, better_a, cur_a);
        index_a = _mm512_mask_mov_epi32(index_a, better_a, cur_index_a);

        const int base_b = next + 16;
        const __m512i cur_b =
            _mm512_loadu_si512(static_cast<const void*>(a + base_b));
        const __m512i cur_index_b =
            _mm512_add_epi32(lanes, _mm512_set1_epi32(base_b));
        const __mmask16 better_b =
            _mm512_cmp_epi32_mask(cur_b, min_b, _MM_CMPINT_LT);
        min_b = _mm512_mask_mov_epi32(min_b, better_b, cur_b);
        index_b = _mm512_mask_mov_epi32(index_b, better_b, cur_index_b);
    }

    if (vector_end - next >= 16) {
        const __m512i cur =
            _mm512_loadu_si512(static_cast<const void*>(a + next));
        const __m512i cur_index =
            _mm512_add_epi32(lanes, _mm512_set1_epi32(next));
        const __mmask16 better =
            _mm512_cmp_epi32_mask(cur, min_a, _MM_CMPINT_LT);
        min_a = _mm512_mask_mov_epi32(min_a, better, cur);
        index_a = _mm512_mask_mov_epi32(index_a, better, cur_index);
    }

    const __m512i lane_minima = _mm512_min_epi32(min_a, min_b);
    const int best_value = _mm512_reduce_min_epi32(lane_minima);
    const __m512i best_value_vector = _mm512_set1_epi32(best_value);
    const __mmask16 best_a = _mm512_cmpeq_epi32_mask(min_a, best_value_vector);
    const __mmask16 best_b = _mm512_cmpeq_epi32_mask(min_b, best_value_vector);
    const __m512i sentinel = _mm512_set1_epi32(INT_MAX);
    const __m512i candidate_a =
        _mm512_mask_mov_epi32(sentinel, best_a, index_a);
    const __m512i candidate_b =
        _mm512_mask_mov_epi32(sentinel, best_b, index_b);
    int best_index = _mm512_reduce_min_epi32(
        _mm512_min_epi32(candidate_a, candidate_b));

    for (int i = vector_end; i < n; ++i) {
        if (a[i] < best_value || (a[i] == best_value && i < best_index)) {
            best_value = a[i];
            best_index = i;
        }
    }

    *result = best_index;
}
