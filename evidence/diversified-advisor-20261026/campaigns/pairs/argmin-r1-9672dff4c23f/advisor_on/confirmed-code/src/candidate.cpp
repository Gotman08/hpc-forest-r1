#include <cstddef>
#include <cstdint>
#if defined(__SSE2__)
#include <emmintrin.h>

static inline void update_minimum(__m128i& best_values,
                                  __m128i& best_blocks,
                                  const __m128i candidate_blocks,
                                  const int32_t* source)
{
    const __m128i values = _mm_load_si128(
        reinterpret_cast<const __m128i*>(source));
    const __m128i take = _mm_cmplt_epi32(values, best_values);
    best_values = _mm_or_si128(_mm_and_si128(take, values),
                               _mm_andnot_si128(take, best_values));
    best_blocks = _mm_or_si128(_mm_and_si128(take, candidate_blocks),
                               _mm_andnot_si128(take, best_blocks));
}

static inline void reduce_min4(__m128i values, __m128i indices,
                               int32_t* min_value, int32_t* min_index)
{
    __m128i other_values = _mm_shuffle_epi32(values, _MM_SHUFFLE(2, 3, 0, 1));
    __m128i other_indices = _mm_shuffle_epi32(indices, _MM_SHUFFLE(2, 3, 0, 1));
    __m128i take_other = _mm_or_si128(
        _mm_cmpgt_epi32(values, other_values),
        _mm_and_si128(_mm_cmpeq_epi32(values, other_values),
                      _mm_cmpgt_epi32(indices, other_indices)));
    values = _mm_or_si128(_mm_and_si128(take_other, other_values),
                          _mm_andnot_si128(take_other, values));
    indices = _mm_or_si128(_mm_and_si128(take_other, other_indices),
                           _mm_andnot_si128(take_other, indices));

    other_values = _mm_shuffle_epi32(values, _MM_SHUFFLE(1, 0, 3, 2));
    other_indices = _mm_shuffle_epi32(indices, _MM_SHUFFLE(1, 0, 3, 2));
    take_other = _mm_or_si128(
        _mm_cmpgt_epi32(values, other_values),
        _mm_and_si128(_mm_cmpeq_epi32(values, other_values),
                      _mm_cmpgt_epi32(indices, other_indices)));
    values = _mm_or_si128(_mm_and_si128(take_other, other_values),
                          _mm_andnot_si128(take_other, values));
    indices = _mm_or_si128(_mm_and_si128(take_other, other_indices),
                           _mm_andnot_si128(take_other, indices));

    *min_value = static_cast<int32_t>(_mm_cvtsi128_si32(values));
    *min_index = static_cast<int32_t>(_mm_cvtsi128_si32(indices));
}
#endif

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

    const int32_t* a = static_cast<const int32_t*>(input1);
#if defined(__SSE2__)
    if (n >= 16) {
        __m128i best_values0 = _mm_load_si128(
            reinterpret_cast<const __m128i*>(a));
        __m128i best_values1 = _mm_load_si128(
            reinterpret_cast<const __m128i*>(a + 4));
        __m128i best_values2 = _mm_load_si128(
            reinterpret_cast<const __m128i*>(a + 8));
        __m128i best_values3 = _mm_load_si128(
            reinterpret_cast<const __m128i*>(a + 12));

        const __m128i first_block = _mm_setzero_si128();
        __m128i best_blocks0 = first_block;
        __m128i best_blocks1 = first_block;
        __m128i best_blocks2 = first_block;
        __m128i best_blocks3 = first_block;

        const __m128i block_step = _mm_set1_epi32(1);
        __m128i candidate_blocks = block_step;
        const std::size_t length = static_cast<std::size_t>(n);
        std::size_t i = 16;
        for (; i + 32 <= length; i += 32) {
            update_minimum(best_values0, best_blocks0, candidate_blocks, a + i);
            update_minimum(best_values1, best_blocks1, candidate_blocks, a + i + 4);
            update_minimum(best_values2, best_blocks2, candidate_blocks, a + i + 8);
            update_minimum(best_values3, best_blocks3, candidate_blocks, a + i + 12);
            candidate_blocks = _mm_add_epi32(candidate_blocks, block_step);

            update_minimum(best_values0, best_blocks0, candidate_blocks, a + i + 16);
            update_minimum(best_values1, best_blocks1, candidate_blocks, a + i + 20);
            update_minimum(best_values2, best_blocks2, candidate_blocks, a + i + 24);
            update_minimum(best_values3, best_blocks3, candidate_blocks, a + i + 28);
            candidate_blocks = _mm_add_epi32(candidate_blocks, block_step);
        }

        if (i + 16 <= length) {
            update_minimum(best_values0, best_blocks0, candidate_blocks, a + i);
            update_minimum(best_values1, best_blocks1, candidate_blocks, a + i + 4);
            update_minimum(best_values2, best_blocks2, candidate_blocks, a + i + 8);
            update_minimum(best_values3, best_blocks3, candidate_blocks, a + i + 12);
            i += 16;
        }

        const __m128i offsets0 = _mm_setr_epi32(0, 1, 2, 3);
        const __m128i offsets1 = _mm_setr_epi32(4, 5, 6, 7);
        const __m128i offsets2 = _mm_setr_epi32(8, 9, 10, 11);
        const __m128i offsets3 = _mm_setr_epi32(12, 13, 14, 15);

        int32_t group_values[4];
        int32_t group_indices[4];
        reduce_min4(best_values0,
                    _mm_add_epi32(_mm_slli_epi32(best_blocks0, 4), offsets0),
                    &group_values[0], &group_indices[0]);
        reduce_min4(best_values1,
                    _mm_add_epi32(_mm_slli_epi32(best_blocks1, 4), offsets1),
                    &group_values[1], &group_indices[1]);
        reduce_min4(best_values2,
                    _mm_add_epi32(_mm_slli_epi32(best_blocks2, 4), offsets2),
                    &group_values[2], &group_indices[2]);
        reduce_min4(best_values3,
                    _mm_add_epi32(_mm_slli_epi32(best_blocks3, 4), offsets3),
                    &group_values[3], &group_indices[3]);

        int32_t best_value = group_values[0];
        int32_t best_index = group_indices[0];
        for (int group = 1; group < 4; ++group) {
            if (group_values[group] < best_value ||
                (group_values[group] == best_value &&
                 group_indices[group] < best_index)) {
                best_value = group_values[group];
                best_index = group_indices[group];
            }
        }

        for (; i < length; ++i) {
            const int32_t value = a[i];
            if (value < best_value ||
                (value == best_value && i < static_cast<std::size_t>(best_index))) {
                best_value = value;
                best_index = static_cast<int32_t>(i);
            }
        }
        *result = static_cast<int>(best_index);
        return;
    }
#endif

    int best_index = 0;
    for (int i = 1; i < n; ++i) {
        if (a[i] < a[best_index]) {
            best_index = i;
        }
    }
    *result = best_index;
}
