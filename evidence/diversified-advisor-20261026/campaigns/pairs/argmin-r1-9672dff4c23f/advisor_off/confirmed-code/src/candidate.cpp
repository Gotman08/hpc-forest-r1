#include <climits>
#if defined(__AVX512F__) || defined(__AVX2__) || defined(__SSE2__)
#include <immintrin.h>
#endif

extern "C" void run(const void* input1, const void* input2, void* output,
                     int n, int parameter, int threads)
{
    const int* a = static_cast<const int*>(input1);
    int* result = static_cast<int*>(output);
    if (n <= 0) {
        *result = 0;
        return;
    }

#if defined(__AVX512F__)
    if (n >= 16) {
        __m512i vmin = _mm512_set1_epi32(INT_MAX);
        int i = 0;
        for (; i <= n - 16; i += 16) {
            const __m512i values = _mm512_loadu_si512(static_cast<const void*>(a + i));
            vmin = _mm512_min_epi32(vmin, values);
        }

        int minimum = _mm512_reduce_min_epi32(vmin);
        for (; i < n; ++i) {
            if (a[i] < minimum) minimum = a[i];
        }

        const __m512i target = _mm512_set1_epi32(minimum);
        int first = n;
        i = 0;
        for (; i <= n - 16; i += 16) {
            const __m512i values = _mm512_loadu_si512(static_cast<const void*>(a + i));
            const unsigned matches = static_cast<unsigned>(_mm512_cmpeq_epi32_mask(values, target));
            if (matches != 0) {
                first = i + __builtin_ctz(matches);
                break;
            }
        }
        if (first == n) {
            for (; i < n; ++i) {
                if (a[i] == minimum) {
                    first = i;
                    break;
                }
            }
        }
        *result = first;
        return;
    }
#endif

#if defined(__AVX2__)
    if (n >= 8) {
        const int vector_end = n - n % 8;
        const __m256i offsets = _mm256_setr_epi32(0, 1, 2, 3, 4, 5, 6, 7);
        const __m256i step = _mm256_set1_epi32(8);
        __m256i min_values = _mm256_loadu_si256(reinterpret_cast<const __m256i*>(a));
        __m256i min_indices = offsets;
        __m256i current_indices = offsets;

        for (int i = 8; i < vector_end; i += 8) {
            current_indices = _mm256_add_epi32(current_indices, step);
            const __m256i values = _mm256_loadu_si256(reinterpret_cast<const __m256i*>(a + i));
            const __m256i smaller = _mm256_cmpgt_epi32(min_values, values);
            min_values = _mm256_blendv_epi8(min_values, values, smaller);
            min_indices = _mm256_blendv_epi8(min_indices, current_indices, smaller);
        }

        int lane_values[8];
        int lane_indices[8];
        _mm256_storeu_si256(reinterpret_cast<__m256i*>(lane_values), min_values);
        _mm256_storeu_si256(reinterpret_cast<__m256i*>(lane_indices), min_indices);

        int best_value = lane_values[0];
        int best_index = lane_indices[0];
        for (int lane = 1; lane < 8; ++lane) {
            if (lane_values[lane] < best_value ||
                (lane_values[lane] == best_value && lane_indices[lane] < best_index)) {
                best_value = lane_values[lane];
                best_index = lane_indices[lane];
            }
        }
        for (int i = vector_end; i < n; ++i) {
            if (a[i] < best_value) {
                best_value = a[i];
                best_index = i;
            }
        }
        *result = best_index;
        return;
    }
#endif

#if defined(__SSE2__)
    if (n >= 4) {
        const int vector_end = n - n % 4;
        __m128i minv = _mm_loadu_si128(reinterpret_cast<const __m128i*>(a));
        for (int i = 4; i < vector_end; i += 4) {
            const __m128i values = _mm_loadu_si128(reinterpret_cast<const __m128i*>(a + i));
            const __m128i choose_values = _mm_cmpgt_epi32(minv, values);
            minv = _mm_or_si128(_mm_and_si128(choose_values, values),
                                _mm_andnot_si128(choose_values, minv));
        }

        int lanes[4];
        _mm_storeu_si128(reinterpret_cast<__m128i*>(lanes), minv);
        int min_value = lanes[0];
        for (int lane = 1; lane < 4; ++lane) {
            if (lanes[lane] < min_value) min_value = lanes[lane];
        }
        for (int i = vector_end; i < n; ++i) {
            if (a[i] < min_value) min_value = a[i];
        }

        const __m128i target = _mm_set1_epi32(min_value);
        for (int base = 0; base < vector_end; base += 4) {
            const __m128i values = _mm_loadu_si128(reinterpret_cast<const __m128i*>(a + base));
            const __m128i equal = _mm_cmpeq_epi32(values, target);
            const unsigned mask = static_cast<unsigned>(_mm_movemask_ps(_mm_castsi128_ps(equal)));
            if (mask != 0) {
                int lane = 0;
                while ((mask & (1u << lane)) == 0) ++lane;
                *result = base + lane;
                return;
            }
        }
        for (int i = vector_end; i < n; ++i) {
            if (a[i] == min_value) {
                *result = i;
                return;
            }
        }
    }
#endif

    int first = 0;
    for (int i = 1; i < n; ++i) {
        if (a[i] < a[first]) first = i;
    }
    *result = first;
}
