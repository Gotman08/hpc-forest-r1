#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#if defined(__SSE2__)
#include <emmintrin.h>
#endif

static bool validate_utf8_scalar(const unsigned char *bytes, size_t length) {
  size_t index = 0;
  while (index < length) {
    const unsigned char byte1 = bytes[index++];
    if (byte1 < 0x80) {
      continue;
    }
    if (byte1 < 0xE0) {
      if (byte1 < 0xC2 || index >= length ||
          (bytes[index++] & 0xC0) != 0x80) {
        return false;
      }
    } else if (byte1 < 0xF0) {
      if (length - index < 2) {
        return false;
      }
      const unsigned char byte2 = bytes[index++];
      if ((byte2 & 0xC0) != 0x80 ||
          (byte1 == 0xE0 && byte2 < 0xA0) ||
          (byte1 == 0xED && byte2 >= 0xA0) ||
          (bytes[index++] & 0xC0) != 0x80) {
        return false;
      }
    } else {
      if (length - index < 3) {
        return false;
      }
      const unsigned char byte2 = bytes[index++];
      if ((byte2 & 0xC0) != 0x80 || byte1 > 0xF4 ||
          (byte1 == 0xF0 && byte2 < 0x90) ||
          (byte1 == 0xF4 && byte2 > 0x8F) ||
          (bytes[index++] & 0xC0) != 0x80 ||
          (bytes[index++] & 0xC0) != 0x80) {
        return false;
      }
    }
  }
  return true;
}

#if defined(__SSE2__)
static bool validate_utf8_sse2(const unsigned char *bytes, size_t length) {
  size_t offset = 0;
  unsigned int carry = 0;

  const __m128i c0 = _mm_set1_epi8(-64);
  const __m128i c1 = _mm_set1_epi8(-63);
  const __m128i df = _mm_set1_epi8(-33);
  const __m128i e0 = _mm_set1_epi8(-32);
  const __m128i ed = _mm_set1_epi8(-19);
  const __m128i ef = _mm_set1_epi8(-17);
  const __m128i f0 = _mm_set1_epi8(-16);
  const __m128i f4 = _mm_set1_epi8(-12);
  const __m128i f5 = _mm_set1_epi8(-11);

  for (; length - offset >= 64; offset += 64) {
    __m128i vectors[4];
    uint64_t continuation_mask = 0;
    uint64_t two_mask = 0;
    uint64_t three_mask = 0;
    uint64_t four_mask = 0;
    uint64_t high_mask = 0;
    uint64_t special_mask = 0;

    for (unsigned int j = 0; j < 4; ++j) {
      vectors[j] = _mm_load_si128(
          reinterpret_cast<const __m128i *>(bytes + offset + 16 * j));
    }

    for (unsigned int j = 0; j < 4; ++j) {
      const __m128i value = vectors[j];
      const __m128i continuation = _mm_cmpgt_epi8(c0, value);
      const __m128i two = _mm_and_si128(_mm_cmpgt_epi8(value, c1),
                                         _mm_cmpgt_epi8(e0, value));
      const __m128i three = _mm_and_si128(_mm_cmpgt_epi8(value, df),
                                           _mm_cmpgt_epi8(f0, value));
      const __m128i four = _mm_and_si128(_mm_cmpgt_epi8(value, ef),
                                          _mm_cmpgt_epi8(f5, value));
      const __m128i special = _mm_or_si128(
          _mm_or_si128(_mm_cmpeq_epi8(value, e0), _mm_cmpeq_epi8(value, ed)),
          _mm_or_si128(_mm_cmpeq_epi8(value, f0), _mm_cmpeq_epi8(value, f4)));
      const unsigned int shift = 16 * j;

      continuation_mask |=
          (uint64_t)(unsigned int)_mm_movemask_epi8(continuation) << shift;
      two_mask |= (uint64_t)(unsigned int)_mm_movemask_epi8(two) << shift;
      three_mask |= (uint64_t)(unsigned int)_mm_movemask_epi8(three) << shift;
      four_mask |= (uint64_t)(unsigned int)_mm_movemask_epi8(four) << shift;
      high_mask |=
          (uint64_t)(unsigned int)_mm_movemask_epi8(value) << shift;
      special_mask |=
          (uint64_t)(unsigned int)_mm_movemask_epi8(special) << shift;
    }

    if ((high_mask & ~(continuation_mask | two_mask | three_mask | four_mask)) != 0) {
      return false;
    }

    uint64_t expected = ((two_mask | three_mask | four_mask) << 1) |
                        ((three_mask | four_mask) << 2) |
                        (four_mask << 3);
    expected |= (UINT64_C(1) << carry) - 1;
    if (continuation_mask != expected) {
      return false;
    }

    while (special_mask != 0) {
      const unsigned int lane = (unsigned int)__builtin_ctzll(
          (unsigned long long)special_mask);
      if (lane == 63 && length - offset == 64) {
        return false;
      }
      const unsigned char lead = bytes[offset + lane];
      const unsigned char second = bytes[offset + lane + 1];
      if ((lead == 0xE0 && second < 0xA0) ||
          (lead == 0xED && second >= 0xA0) ||
          (lead == 0xF0 && second < 0x90) ||
          (lead == 0xF4 && second > 0x8F)) {
        return false;
      }
      special_mask &= special_mask - 1;
    }

    const uint64_t outgoing =
        ((two_mask | three_mask | four_mask) >> 63) |
        ((three_mask | four_mask) >> 62) | (four_mask >> 61);
    carry = (unsigned int)((outgoing & 1) + ((outgoing >> 1) & 1) +
                           ((outgoing >> 2) & 1));
  }

  const size_t remaining = length - offset;
  if (carry > remaining) {
    return false;
  }
  for (unsigned int i = 0; i < carry; ++i) {
    if ((bytes[offset + i] & 0xC0) != 0x80) {
      return false;
    }
  }
  if (remaining == carry) {
    return true;
  }
  return validate_utf8_scalar(bytes + offset + carry, remaining - carry);
}
#endif

static bool validate_utf8(const char *b, size_t length) {
  const unsigned char *bytes = (const unsigned char *)b;
#if defined(__SSE2__)
  return validate_utf8_sse2(bytes, length);
#else
  return validate_utf8_scalar(bytes, length);
#endif
}

extern "C" void run(const void *input1, const void *input2, void *output,
                    int n, int parameter, int threads) {
  *(uint32_t *)output = validate_utf8((const char *)input1, n);
}
