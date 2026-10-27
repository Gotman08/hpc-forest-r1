#include <cstddef>
#include <cstdint>
#include <cstring>

#if defined(__SSE2__)
#include <emmintrin.h>
#define UTF8_HAVE_SSE2 1
#else
#define UTF8_HAVE_SSE2 0
#endif

static inline bool invalid_second_byte(unsigned char lead, unsigned char second) {
  return (lead == 0xE0 && second < 0xA0) ||
         (lead == 0xED && second >= 0xA0) ||
         (lead == 0xF0 && second < 0x90) ||
         (lead == 0xF4 && second > 0x8F);
}

static bool validate_utf8_scalar(const unsigned char *bytes, size_t length,
                                 size_t index, unsigned pending,
                                 unsigned char preceding_lead) {
  bool check_pending_second = pending != 0;
  while (index < length) {
    const unsigned char byte1 = bytes[index++];

    if (pending != 0) {
      if ((byte1 & 0xC0) != 0x80 ||
          (check_pending_second &&
           invalid_second_byte(preceding_lead, byte1))) {
        return false;
      }
      --pending;
      check_pending_second = false;
      continue;
    }

    if (byte1 < 0x80) {
      continue;
    }
    if (byte1 >= 0xC2 && byte1 <= 0xDF) {
      if (index >= length || (bytes[index++] & 0xC0) != 0x80) {
        return false;
      }
      continue;
    }
    if (byte1 >= 0xE0 && byte1 <= 0xEF) {
      if (length - index < 2) {
        return false;
      }
      const unsigned char byte2 = bytes[index++];
      const unsigned char byte3 = bytes[index++];
      if ((byte2 & 0xC0) != 0x80 || invalid_second_byte(byte1, byte2) ||
          (byte3 & 0xC0) != 0x80) {
        return false;
      }
      continue;
    }
    if (byte1 >= 0xF0 && byte1 <= 0xF4) {
      if (length - index < 3) {
        return false;
      }
      const unsigned char byte2 = bytes[index++];
      const unsigned char byte3 = bytes[index++];
      const unsigned char byte4 = bytes[index++];
      if ((byte2 & 0xC0) != 0x80 || invalid_second_byte(byte1, byte2) ||
          (byte3 & 0xC0) != 0x80 || (byte4 & 0xC0) != 0x80) {
        return false;
      }
      continue;
    }
    return false;
  }
  return pending == 0;
}

#if UTF8_HAVE_SSE2
static inline __m128i unsigned_byte_ge(__m128i value, int bound,
                                      __m128i sign_bit) {
  const __m128i ordered = _mm_xor_si128(value, sign_bit);
  return _mm_cmpgt_epi8(ordered, _mm_set1_epi8(static_cast<char>(bound - 129)));
}

static inline __m128i unsigned_byte_gt(__m128i value, int bound,
                                      __m128i sign_bit) {
  const __m128i ordered = _mm_xor_si128(value, sign_bit);
  return _mm_cmpgt_epi8(ordered, _mm_set1_epi8(static_cast<char>(bound - 128)));
}

static inline __m128i unsigned_byte_lt(__m128i value, int bound,
                                      __m128i sign_bit) {
  const __m128i ordered = _mm_xor_si128(value, sign_bit);
  return _mm_cmpgt_epi8(_mm_set1_epi8(static_cast<char>(bound - 128)), ordered);
}

static inline __m128i unsigned_byte_le(__m128i value, int bound,
                                      __m128i sign_bit, __m128i all_bits) {
  return _mm_xor_si128(unsigned_byte_gt(value, bound, sign_bit), all_bits);
}

static bool validate_utf8_sse2(const unsigned char *bytes, size_t length) {
  const __m128i zero = _mm_setzero_si128();
  const __m128i all_bits = _mm_set1_epi8(static_cast<char>(-1));
  const __m128i sign_bit = _mm_set1_epi8(static_cast<char>(-128));
  size_t index = 0;
  uint32_t pending_mask = 0;
  unsigned char last_byte = 0;

  while (length - index >= 16) {
    const __m128i block = _mm_loadu_si128(
        reinterpret_cast<const __m128i *>(bytes + index));

    const __m128i ascii = _mm_xor_si128(_mm_cmpgt_epi8(zero, block), all_bits);
    const __m128i continuation = _mm_and_si128(
        unsigned_byte_ge(block, 0x80, sign_bit),
        unsigned_byte_le(block, 0xBF, sign_bit, all_bits));
    const __m128i lead2 = _mm_and_si128(
        unsigned_byte_ge(block, 0xC2, sign_bit),
        unsigned_byte_le(block, 0xDF, sign_bit, all_bits));
    const __m128i lead3 = _mm_and_si128(
        unsigned_byte_ge(block, 0xE0, sign_bit),
        unsigned_byte_le(block, 0xEF, sign_bit, all_bits));
    const __m128i lead4 = _mm_and_si128(
        unsigned_byte_ge(block, 0xF0, sign_bit),
        unsigned_byte_le(block, 0xF4, sign_bit, all_bits));

    __m128i valid = _mm_or_si128(ascii, continuation);
    valid = _mm_or_si128(valid, lead2);
    valid = _mm_or_si128(valid, lead3);
    valid = _mm_or_si128(valid, lead4);
    if (_mm_movemask_epi8(_mm_xor_si128(valid, all_bits)) != 0) {
      return false;
    }

    const __m128i previous = _mm_slli_si128(block, 1);
    const __m128i previous_e0 = _mm_cmpeq_epi8(previous, _mm_set1_epi8(-32));
    const __m128i previous_ed = _mm_cmpeq_epi8(previous, _mm_set1_epi8(-19));
    const __m128i previous_f0 = _mm_cmpeq_epi8(previous, _mm_set1_epi8(-16));
    const __m128i previous_f4 = _mm_cmpeq_epi8(previous, _mm_set1_epi8(-12));
    const __m128i bad_second = _mm_or_si128(
        _mm_or_si128(
            _mm_and_si128(previous_e0,
                           unsigned_byte_lt(block, 0xA0, sign_bit)),
            _mm_and_si128(previous_ed,
                           unsigned_byte_ge(block, 0xA0, sign_bit))),
        _mm_or_si128(
            _mm_and_si128(previous_f0,
                           unsigned_byte_lt(block, 0x90, sign_bit)),
            _mm_and_si128(previous_f4,
                           unsigned_byte_gt(block, 0x8F, sign_bit))));
    if (_mm_movemask_epi8(bad_second) != 0) {
      return false;
    }

    const uint32_t continuation_bits =
        static_cast<uint32_t>(_mm_movemask_epi8(continuation));
    const uint32_t lead2_bits =
        static_cast<uint32_t>(_mm_movemask_epi8(lead2));
    const uint32_t lead3_bits =
        static_cast<uint32_t>(_mm_movemask_epi8(lead3));
    const uint32_t lead4_bits =
        static_cast<uint32_t>(_mm_movemask_epi8(lead4));
    const uint32_t expected =
        ((lead2_bits | lead3_bits | lead4_bits) << 1) |
        ((lead3_bits | lead4_bits) << 2) | (lead4_bits << 3);
    const uint32_t expected_here = (expected & 0xFFFFU) | pending_mask;
    if (continuation_bits != expected_here) {
      return false;
    }

    if (pending_mask != 0 &&
        invalid_second_byte(last_byte, bytes[index])) {
      return false;
    }
    pending_mask = expected >> 16;
    last_byte = bytes[index + 15];
    index += 16;
  }

  unsigned pending = 0;
  while (pending < 3 && (pending_mask & (1U << pending)) != 0) {
    ++pending;
  }
  if ((pending_mask >> pending) != 0) {
    return false;
  }
  return validate_utf8_scalar(bytes, length, index, pending, last_byte);
}
#endif

static bool validate_utf8(const unsigned char *bytes, size_t length) {
#if UTF8_HAVE_SSE2
  return validate_utf8_sse2(bytes, length);
#else
  return validate_utf8_scalar(bytes, length, 0, 0, 0);
#endif
}

extern "C" void run(const void *input1, const void *input2, void *output,
                    int n, int parameter, int threads) {
  (void)input2;
  (void)parameter;
  (void)threads;
  const size_t length = n > 0 ? static_cast<size_t>(n) : 0;
  const unsigned char *bytes =
      static_cast<const unsigned char *>(input1);
  const uint32_t result = validate_utf8(bytes, length) ? 1U : 0U;
  std::memcpy(output, &result, sizeof(result));
}
