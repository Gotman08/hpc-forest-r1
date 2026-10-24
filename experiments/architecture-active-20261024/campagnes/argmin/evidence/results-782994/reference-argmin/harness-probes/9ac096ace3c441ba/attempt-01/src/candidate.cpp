#include <climits>
#include <immintrin.h>

extern "C" __attribute__((target("avx512f")))
void run(const void* input1, const void* input2, void* output, int n,
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
        int best = 0;
        for (int i = 1; i < n; ++i) {
            if (a[i] < a[best]) best = i;
        }
        *result = best;
        return;
    }

    const int vector_end = n - n % 16;
    const __m512i lanes = _mm512_set_epi32(15, 14, 13, 12, 11, 10, 9, 8,
                                           7, 6, 5, 4, 3, 2, 1, 0);
    __m512i min_a = _mm512_loadu_si512(static_cast<const void*>(a));
    __m512i index_a = lanes;

    // The second state is a non-winning sentinel unless a second vector exists.
    __m512i min_b = _mm512_set1_epi32(INT_MAX);
    __m512i index_b = _mm512_set1_epi32(INT_MAX);
    if (vector_end >= 32) {
        min_b = _mm512_loadu_si512(static_cast<const void*>(a + 16));
        index_b = _mm512_add_epi32(lanes, _mm512_set1_epi32(16));
    }

    // Interleave two independent lane-state streams to shorten each dependency chain.
    int next = 32;
    for (; vector_end - next >= 32; next += 32) {
        const __m512i cur_a = _mm512_loadu_si512(static_cast<const void*>(a + next));
        const __m512i cur_index_a =
            _mm512_add_epi32(lanes, _mm512_set1_epi32(next));
        const __mmask16 better_a = _mm512_cmp_epi32_mask(cur_a, min_a, _MM_CMPINT_LT);
        min_a = _mm512_mask_mov_epi32(min_a, better_a, cur_a);
        index_a = _mm512_mask_mov_epi32(index_a, better_a, cur_index_a);

        const int base_b = next + 16;
        const __m512i cur_b = _mm512_loadu_si512(static_cast<const void*>(a + base_b));
        const __m512i cur_index_b =
            _mm512_add_epi32(lanes, _mm512_set1_epi32(base_b));
        const __mmask16 better_b = _mm512_cmp_epi32_mask(cur_b, min_b, _MM_CMPINT_LT);
        min_b = _mm512_mask_mov_epi32(min_b, better_b, cur_b);
        index_b = _mm512_mask_mov_epi32(index_b, better_b, cur_index_b);
    }

    // An unmatched complete vector belongs to the first state.
    if (vector_end - next >= 16) {
        const __m512i cur = _mm512_loadu_si512(static_cast<const void*>(a + next));
        const __m512i cur_index = _mm512_add_epi32(lanes, _mm512_set1_epi32(next));
        const __mmask16 better = _mm512_cmp_epi32_mask(cur, min_a, _MM_CMPINT_LT);
        min_a = _mm512_mask_mov_epi32(min_a, better, cur);
        index_a = _mm512_mask_mov_epi32(index_a, better, cur_index);
    }

    int values_a[16], indices_a[16], values_b[16], indices_b[16];
    _mm512_storeu_si512(static_cast<void*>(values_a), min_a);
    _mm512_storeu_si512(static_cast<void*>(indices_a), index_a);
    _mm512_storeu_si512(static_cast<void*>(values_b), min_b);
    _mm512_storeu_si512(static_cast<void*>(indices_b), index_b);

    int best_value = values_a[0];
    int best_index = indices_a[0];
    for (int lane = 1; lane < 16; ++lane) {
        if (values_a[lane] < best_value ||
            (values_a[lane] == best_value && indices_a[lane] < best_index)) {
            best_value = values_a[lane];
            best_index = indices_a[lane];
        }
        if (values_b[lane] < best_value ||
            (values_b[lane] == best_value && indices_b[lane] < best_index)) {
            best_value = values_b[lane];
            best_index = indices_b[lane];
        }
    }

    for (int i = vector_end; i < n; ++i) {
        if (a[i] < best_value || (a[i] == best_value && i < best_index)) {
            best_value = a[i];
            best_index = i;
        }
    }

    *result = best_index;
}
