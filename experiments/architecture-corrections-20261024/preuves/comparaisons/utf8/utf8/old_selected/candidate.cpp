#include <cstddef>
#include <cstdint>
#include <emmintrin.h>

static inline __m128i lead2_mask(__m128i value) {
  return _mm_and_si128(
      _mm_cmpgt_epi8(value, _mm_set1_epi8(static_cast<char>(0xC1))),
      _mm_cmpgt_epi8(_mm_set1_epi8(static_cast<char>(0xE0)), value));
}

static inline __m128i lead3_mask(__m128i value) {
  return _mm_and_si128(
      _mm_cmpgt_epi8(value, _mm_set1_epi8(static_cast<char>(0xDF))),
      _mm_cmpgt_epi8(_mm_set1_epi8(static_cast<char>(0xF0)), value));
}

static inline __m128i lead4_mask(__m128i value) {
  return _mm_and_si128(
      _mm_cmpgt_epi8(value, _mm_set1_epi8(static_cast<char>(0xEF))),
      _mm_cmpgt_epi8(_mm_set1_epi8(static_cast<char>(0xF5)), value));
}

static inline bool validate_simd_block(const unsigned char *bytes,
                                       size_t offset, __m128i &previous,
                                       unsigned int carry,
                                       unsigned int &next_carry) {
  const __m128i current = _mm_loadu_si128(
      reinterpret_cast<const __m128i *>(bytes + offset));
  const __m128i prior1 = _mm_or_si128(
      _mm_slli_si128(current, 1), _mm_srli_si128(previous, 15));
  const __m128i zero = _mm_setzero_si128();
  const __m128i ones = _mm_set1_epi8(static_cast<char>(-1));
  const __m128i high_bit = _mm_cmpgt_epi8(zero, current);
  const __m128i ascii = _mm_andnot_si128(high_bit, ones);
  const __m128i continuation = _mm_cmpeq_epi8(
      _mm_and_si128(current, _mm_set1_epi8(static_cast<char>(0xC0))),
      _mm_set1_epi8(static_cast<char>(0x80)));
  const __m128i lead2 = lead2_mask(current);
  const __m128i lead3 = lead3_mask(current);
  const __m128i lead4 = lead4_mask(current);
  const __m128i allowed = _mm_or_si128(
      _mm_or_si128(ascii, continuation),
      _mm_or_si128(_mm_or_si128(lead2, lead3), lead4));
  const __m128i invalid_bytes = _mm_andnot_si128(allowed, ones);
  if (_mm_movemask_epi8(invalid_bytes) != 0) {
    return false;
  }

  const unsigned int lead2_bits =
      static_cast<unsigned int>(_mm_movemask_epi8(lead2));
  const unsigned int lead3_bits =
      static_cast<unsigned int>(_mm_movemask_epi8(lead3));
  const unsigned int lead4_bits =
      static_cast<unsigned int>(_mm_movemask_epi8(lead4));
  const unsigned int expected =
      carry | ((lead2_bits | lead3_bits | lead4_bits) << 1) |
      ((lead3_bits | lead4_bits) << 2) | (lead4_bits << 3);
  const unsigned int continuation_bits =
      static_cast<unsigned int>(_mm_movemask_epi8(continuation));
  if (continuation_bits != (expected & 0xFFFFu)) {
    return false;
  }
  next_carry = expected >> 16;

  const __m128i unsigned_current = _mm_xor_si128(
      current, _mm_set1_epi8(static_cast<char>(0x80)));
  const __m128i below_a0 = _mm_cmplt_epi8(
      unsigned_current, _mm_set1_epi8(static_cast<char>(0x20)));
  const __m128i below_90 = _mm_cmplt_epi8(
      unsigned_current, _mm_set1_epi8(static_cast<char>(0x10)));
  const __m128i above_8f = _mm_cmpgt_epi8(
      unsigned_current, _mm_set1_epi8(static_cast<char>(0x0F)));
  const __m128i prev_e0 = _mm_cmpeq_epi8(
      prior1, _mm_set1_epi8(static_cast<char>(0xE0)));
  const __m128i prev_ed = _mm_cmpeq_epi8(
      prior1, _mm_set1_epi8(static_cast<char>(0xED)));
  const __m128i prev_f0 = _mm_cmpeq_epi8(
      prior1, _mm_set1_epi8(static_cast<char>(0xF0)));
  const __m128i prev_f4 = _mm_cmpeq_epi8(
      prior1, _mm_set1_epi8(static_cast<char>(0xF4)));
  const __m128i restricted_range_error = _mm_or_si128(
      _mm_or_si128(_mm_and_si128(prev_e0, below_a0),
                   _mm_and_si128(prev_ed, _mm_andnot_si128(below_a0, ones))),
      _mm_or_si128(_mm_and_si128(prev_f0, below_90),
                   _mm_and_si128(prev_f4, above_8f)));
  if (_mm_movemask_epi8(restricted_range_error) != 0) {
    return false;
  }

  previous = current;
  return true;
}

static bool validate_scalar_from(const unsigned char *bytes, size_t length,
                                 size_t index) {
  while (index < length) {
    const unsigned char first = bytes[index++];
    if (first < 0x80) {
      continue;
    }
    if (first <= 0xDF) {
      if (first < 0xC2 || length - index < 1) {
        return false;
      }
      if ((bytes[index++] & 0xC0) != 0x80) {
        return false;
      }
    } else if (first <= 0xEF) {
      if (length - index < 2) {
        return false;
      }
      const unsigned char second = bytes[index++];
      if ((second & 0xC0) != 0x80 ||
          (first == 0xE0 && second < 0xA0) ||
          (first == 0xED && second >= 0xA0) ||
          (bytes[index++] & 0xC0) != 0x80) {
        return false;
      }
    } else if (first <= 0xF4) {
      if (length - index < 3) {
        return false;
      }
      const unsigned char second = bytes[index++];
      if ((second & 0xC0) != 0x80 ||
          (first == 0xF0 && second < 0x90) ||
          (first == 0xF4 && second > 0x8F) ||
          (bytes[index++] & 0xC0) != 0x80 ||
          (bytes[index++] & 0xC0) != 0x80) {
        return false;
      }
    } else {
      return false;
    }
  }
  return true;
}

static bool validate_utf8(const char *input, size_t length) {
  const unsigned char *bytes =
      reinterpret_cast<const unsigned char *>(input);
  __m128i previous = _mm_setzero_si128();
  size_t offset = 0;
  unsigned int carry = 0;

  // Test a 32-byte outer unroll using two ordered 16-byte SIMD blocks.
  while (length - offset >= 32) {
    unsigned int next_carry = 0;
    if (!validate_simd_block(bytes, offset, previous, carry, next_carry)) {
      return false;
    }
    carry = next_carry;
    if (!validate_simd_block(bytes, offset + 16, previous, carry,
                             next_carry)) {
      return false;
    }
    carry = next_carry;
    offset += 32;
  }

  while (length - offset >= 16) {
    unsigned int next_carry = 0;
    if (!validate_simd_block(bytes, offset, previous, carry, next_carry)) {
      return false;
    }
    carry = next_carry;
    offset += 16;
  }

  if (carry != 0) {
    size_t tail_start = offset - 3;
    while (tail_start > 0 && (bytes[tail_start] & 0xC0) == 0x80) {
      --tail_start;
    }
    return validate_scalar_from(bytes, length, tail_start);
  }
  return validate_scalar_from(bytes, length, offset);
}

extern "C" void run(const void *input1, const void *input2, void *output,
                    int n, int parameter, int threads) {
  (void)input2;
  (void)parameter;
  (void)threads;
  const bool valid =
      n >= 0 && validate_utf8(static_cast<const char *>(input1),
                              static_cast<size_t>(n));
  *static_cast<uint32_t *>(output) = valid ? 1u : 0u;
}
