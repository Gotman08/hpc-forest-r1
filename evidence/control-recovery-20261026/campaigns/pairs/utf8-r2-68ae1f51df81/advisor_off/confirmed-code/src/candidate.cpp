#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#if defined(__AVX2__)
#include <immintrin.h>
#elif defined(__SSE2__)
#include <emmintrin.h>
#endif

static bool validate_scalar_tail(const unsigned char *bytes, size_t length,
                                 size_t index, unsigned pending) {
  while (index < length) {
    unsigned char byte = bytes[index];
    if (pending != 0) {
      if ((byte & 0xC0) != 0x80) {
        return false;
      }
      --pending;
      ++index;
      continue;
    }

    if (byte < 0x80) {
      ++index;
    } else if (byte < 0xE0) {
      if (length - index < 2 || byte < 0xC2 || byte > 0xDF ||
          (bytes[index + 1] & 0xC0) != 0x80) {
        return false;
      }
      index += 2;
    } else if (byte < 0xF0) {
      if (length - index < 3 ||
          (bytes[index + 1] & 0xC0) != 0x80 ||
          (byte == 0xE0 && bytes[index + 1] < 0xA0) ||
          (byte == 0xED && bytes[index + 1] >= 0xA0) ||
          (bytes[index + 2] & 0xC0) != 0x80) {
        return false;
      }
      index += 3;
    } else {
      if (length - index < 4 || byte > 0xF4 ||
          (bytes[index + 1] & 0xC0) != 0x80 ||
          (byte == 0xF0 && bytes[index + 1] < 0x90) ||
          (byte == 0xF4 && bytes[index + 1] > 0x8F) ||
          (bytes[index + 2] & 0xC0) != 0x80 ||
          (bytes[index + 3] & 0xC0) != 0x80) {
        return false;
      }
      index += 4;
    }
  }
  return pending == 0;
}

#if defined(__AVX2__)
#define VALIDATE_AVX2_BLOCK(OFFSET, OKFLAG) do { \
  const __m256i value = \
      _mm256_loadu_si256((const __m256i *)(bytes + index + (OFFSET))); \
  const __m256i next = \
      _mm256_loadu_si256((const __m256i *)(bytes + index + (OFFSET) + 1)); \
  const __m256i high_order = _mm256_xor_si256(value, high_bit); \
  const __m256i next_order = _mm256_xor_si256(next, high_bit); \
  const uint32_t ascii = (uint32_t)~_mm256_movemask_epi8(value); \
  const __m256i continuation_bytes = _mm256_cmpeq_epi8( \
      _mm256_and_si256(value, mask_c0), cont_value); \
  const uint32_t continuation = \
      (uint32_t)_mm256_movemask_epi8(continuation_bytes); \
  const __m256i two_pattern = _mm256_cmpeq_epi8( \
      _mm256_and_si256(value, mask_e0), c0); \
  const __m256i is_c0 = _mm256_cmpeq_epi8(value, c0); \
  const __m256i is_c1 = _mm256_cmpeq_epi8(value, c1); \
  const uint32_t lead2 = (uint32_t)_mm256_movemask_epi8( \
      _mm256_andnot_si256(_mm256_or_si256(is_c0, is_c1), two_pattern)); \
  const uint32_t lead3 = (uint32_t)_mm256_movemask_epi8( \
      _mm256_cmpeq_epi8(_mm256_and_si256(value, mask_f0), mask_e0)); \
  const __m256i at_least_f0 = \
      _mm256_cmpgt_epi8(high_order, unsigned_order_min); \
  const __m256i below_f5 = \
      _mm256_cmpgt_epi8(unsigned_order_max_plus_one, high_order); \
  const uint32_t lead4 = (uint32_t)_mm256_movemask_epi8( \
      _mm256_and_si256(at_least_f0, below_f5)); \
  const bool category_ok = \
      (ascii | continuation | lead2 | lead3 | lead4) == 0xFFFFFFFFu; \
  const __m256i bad_e0 = _mm256_and_si256( \
      _mm256_cmpeq_epi8(value, e0), _mm256_cmpgt_epi8(order_20, next_order)); \
  const __m256i bad_ed = _mm256_and_si256( \
      _mm256_cmpeq_epi8(value, ed), _mm256_cmpgt_epi8(next_order, order_1f)); \
  const __m256i bad_f0 = _mm256_and_si256( \
      _mm256_cmpeq_epi8(value, f0), _mm256_cmpgt_epi8(order_10, next_order)); \
  const __m256i bad_f4 = _mm256_and_si256( \
      _mm256_cmpeq_epi8(value, f4), _mm256_cmpgt_epi8(next_order, order_0f)); \
  const __m256i special_bad = _mm256_or_si256( \
      _mm256_or_si256(bad_e0, bad_ed), _mm256_or_si256(bad_f0, bad_f4)); \
  const bool special_ok = _mm256_movemask_epi8(special_bad) == 0; \
  const uint64_t expected = \
      ((uint64_t)(lead2 | lead3 | lead4) << 1) | \
      ((uint64_t)(lead3 | lead4) << 2) | ((uint64_t)lead4 << 3); \
  const bool continuation_ok = \
      (uint32_t)(expected | carry) == continuation; \
  (OKFLAG) = category_ok & special_ok & continuation_ok; \
  carry = (uint32_t)(expected >> 32); \
} while (0)

static bool validate_utf8(const unsigned char *bytes, size_t length) {
  size_t index = 0;
  uint32_t carry = 0;
  const __m256i mask_c0 = _mm256_set1_epi8(-64);
  const __m256i mask_e0 = _mm256_set1_epi8(-32);
  const __m256i mask_f0 = _mm256_set1_epi8(-16);
  const __m256i c0 = _mm256_set1_epi8(-64);
  const __m256i c1 = _mm256_set1_epi8(-63);
  const __m256i cont_value = _mm256_set1_epi8(-128);
  const __m256i high_bit = _mm256_set1_epi8(-128);
  const __m256i unsigned_order_min = _mm256_set1_epi8(111);
  const __m256i unsigned_order_max_plus_one = _mm256_set1_epi8(117);
  const __m256i order_20 = _mm256_set1_epi8(32);
  const __m256i order_1f = _mm256_set1_epi8(31);
  const __m256i order_10 = _mm256_set1_epi8(16);
  const __m256i order_0f = _mm256_set1_epi8(15);
  const __m256i e0 = _mm256_set1_epi8(-32);
  const __m256i ed = _mm256_set1_epi8(-19);
  const __m256i f0 = _mm256_set1_epi8(-16);
  const __m256i f4 = _mm256_set1_epi8(-12);

  // Collect each block's checks and decide once per six-block group.
  bool block0_ok;
  bool block1_ok;
  bool block2_ok;
  bool block3_ok;
  bool block4_ok;
  bool block5_ok;
  while (length - index > 192) {
    VALIDATE_AVX2_BLOCK(0, block0_ok);
    VALIDATE_AVX2_BLOCK(32, block1_ok);
    VALIDATE_AVX2_BLOCK(64, block2_ok);
    VALIDATE_AVX2_BLOCK(96, block3_ok);
    VALIDATE_AVX2_BLOCK(128, block4_ok);
    VALIDATE_AVX2_BLOCK(160, block5_ok);
    if (!(block0_ok & block1_ok & block2_ok &
          block3_ok & block4_ok & block5_ok)) {
      return false;
    }
    index += 192;
  }

  // Process any complete blocks left after the grouped loop.
  bool block_ok;
  while (length - index > 32) {
    VALIDATE_AVX2_BLOCK(0, block_ok);
    if (!block_ok) {
      return false;
    }
    index += 32;
  }

  unsigned pending = 0;
  while (carry != 0) {
    if ((carry & 1u) == 0) {
      return false;
    }
    ++pending;
    carry >>= 1;
  }
  return validate_scalar_tail(bytes, length, index, pending);
}
#undef VALIDATE_AVX2_BLOCK
#elif defined(__SSE2__)
static bool validate_utf8(const unsigned char *bytes, size_t length) {
  size_t index = 0;
  uint16_t carry = 0;
  const __m128i mask_c0 = _mm_set1_epi8(-64);
  const __m128i mask_e0 = _mm_set1_epi8(-32);
  const __m128i mask_f0 = _mm_set1_epi8(-16);
  const __m128i c0 = _mm_set1_epi8(-64);
  const __m128i c1 = _mm_set1_epi8(-63);
  const __m128i cont_value = _mm_set1_epi8(-128);
  const __m128i high_bit = _mm_set1_epi8(-128);
  const __m128i unsigned_order_min = _mm_set1_epi8(111);
  const __m128i unsigned_order_max_plus_one = _mm_set1_epi8(117);
  const __m128i order_20 = _mm_set1_epi8(32);
  const __m128i order_1f = _mm_set1_epi8(31);
  const __m128i order_10 = _mm_set1_epi8(16);
  const __m128i order_0f = _mm_set1_epi8(15);

  // Keep one byte of lookahead available for the lead-specific restrictions.
  // Both unaligned vector loads stay wholly within [0, length).
  while (length - index > 16) {
    const __m128i value =
        _mm_loadu_si128((const __m128i *)(bytes + index));
    const __m128i next =
        _mm_loadu_si128((const __m128i *)(bytes + index + 1));
    const __m128i high_order = _mm_xor_si128(value, high_bit);
    const __m128i next_order = _mm_xor_si128(next, high_bit);

    const uint16_t ascii = (uint16_t)~_mm_movemask_epi8(value);
    const __m128i continuation_bytes =
        _mm_cmpeq_epi8(_mm_and_si128(value, mask_c0), cont_value);
    const uint16_t continuation =
        (uint16_t)_mm_movemask_epi8(continuation_bytes);

    const __m128i two_pattern =
        _mm_cmpeq_epi8(_mm_and_si128(value, mask_e0), c0);
    const __m128i is_c0 = _mm_cmpeq_epi8(value, c0);
    const __m128i is_c1 = _mm_cmpeq_epi8(value, c1);
    const uint16_t lead2 = (uint16_t)_mm_movemask_epi8(
        _mm_andnot_si128(_mm_or_si128(is_c0, is_c1), two_pattern));

    const uint16_t lead3 = (uint16_t)_mm_movemask_epi8(
        _mm_cmpeq_epi8(_mm_and_si128(value, mask_f0), mask_e0));

    const __m128i at_least_f0 = _mm_cmpgt_epi8(high_order, unsigned_order_min);
    const __m128i below_f5 = _mm_cmpgt_epi8(unsigned_order_max_plus_one, high_order);
    const uint16_t lead4 = (uint16_t)_mm_movemask_epi8(
        _mm_and_si128(at_least_f0, below_f5));

    if ((uint16_t)(ascii | continuation | lead2 | lead3 | lead4) != 0xFFFF) {
      return false;
    }

    const __m128i e0 = _mm_cmpeq_epi8(value, _mm_set1_epi8(-32));
    const __m128i ed = _mm_cmpeq_epi8(value, _mm_set1_epi8(-19));
    const __m128i f0 = _mm_cmpeq_epi8(value, _mm_set1_epi8(-16));
    const __m128i f4 = _mm_cmpeq_epi8(value, _mm_set1_epi8(-12));
    const __m128i bad_e0 = _mm_and_si128(e0, _mm_cmpgt_epi8(order_20, next_order));
    const __m128i bad_ed = _mm_and_si128(ed, _mm_cmpgt_epi8(next_order, order_1f));
    const __m128i bad_f0 = _mm_and_si128(f0, _mm_cmpgt_epi8(order_10, next_order));
    const __m128i bad_f4 = _mm_and_si128(f4, _mm_cmpgt_epi8(next_order, order_0f));
    const __m128i special_bad = _mm_or_si128(
        _mm_or_si128(bad_e0, bad_ed), _mm_or_si128(bad_f0, bad_f4));
    if (_mm_movemask_epi8(special_bad) != 0) {
      return false;
    }

    const uint32_t expected =
        ((uint32_t)(lead2 | lead3 | lead4) << 1) |
        ((uint32_t)(lead3 | lead4) << 2) |
        ((uint32_t)lead4 << 3);
    if ((uint16_t)((uint16_t)expected | carry) != continuation) {
      return false;
    }
    carry = (uint16_t)(expected >> 16);
    index += 16;
  }

  unsigned pending = 0;
  while (carry != 0) {
    if ((carry & 1u) == 0) {
      return false;
    }
    ++pending;
    carry >>= 1;
  }
  return validate_scalar_tail(bytes, length, index, pending);
}
#else
static bool validate_utf8(const unsigned char *bytes, size_t length) {
  return validate_scalar_tail(bytes, length, 0, 0);
}
#endif

extern "C" void run(const void *input1, const void *input2, void *output,
                    int n, int parameter, int threads) {
  (void)input2;
  (void)parameter;
  (void)threads;
  const bool valid = n >= 0 &&
      validate_utf8((const unsigned char *)input1, (size_t)(n < 0 ? 0 : n));
  *(uint32_t *)output = valid ? 1u : 0u;
}
