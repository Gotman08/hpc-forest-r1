#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <cstring>

static bool validate_utf8_scalar(const unsigned char *bytes, size_t length) {
  for (size_t index = 0;;) {
    unsigned char byte1;

    do {
      if (index >= length) {
        return true;
      }
      byte1 = bytes[index++];
    } while (byte1 < 0x80);

    if (byte1 < 0xE0) {
      if (index == length || byte1 < 0xC2 ||
          (bytes[index++] & 0xC0) != 0x80) {
        return false;
      }
    } else if (byte1 < 0xF0) {
      if (index + 1 >= length) {
        return false;
      }
      unsigned char byte2 = bytes[index++];
      if ((byte2 & 0xC0) != 0x80 ||
          (byte1 == 0xE0 && byte2 < 0xA0) ||
          (byte1 == 0xED && byte2 >= 0xA0) ||
          (bytes[index++] & 0xC0) != 0x80) {
        return false;
      }
    } else {
      if (index + 2 >= length) {
        return false;
      }
      unsigned char byte2 = bytes[index++];
      if ((byte2 & 0xC0) != 0x80 || byte1 > 0xF4 ||
          (byte1 == 0xF0 && byte2 < 0x90) ||
          (byte1 == 0xF4 && byte2 > 0x8F) ||
          (bytes[index++] & 0xC0) != 0x80 ||
          (bytes[index++] & 0xC0) != 0x80) {
        return false;
      }
    }
  }
}

#if (defined(__GNUC__) || defined(__clang__)) && (defined(__x86_64__) || defined(__i386__))
#include <immintrin.h>

static inline __attribute__((target("avx2"))) bool validate_avx2_block(
    const unsigned char *bytes, size_t offset, size_t length,
    uint32_t *carry) {
  const __m256i value = _mm256_loadu_si256(
      reinterpret_cast<const __m256i *>(bytes + offset));
  const __m256i zero = _mm256_setzero_si256();
  const __m256i high_bytes = _mm256_cmpgt_epi8(zero, value);

  const __m256i continuation = _mm256_andnot_si256(
      _mm256_cmpgt_epi8(value, _mm256_set1_epi8(-65)), high_bytes);
  const __m256i lead2 = _mm256_and_si256(
      _mm256_cmpgt_epi8(value, _mm256_set1_epi8(-63)),
      _mm256_cmpgt_epi8(_mm256_set1_epi8(-32), value));
  const __m256i lead3 = _mm256_and_si256(
      _mm256_cmpgt_epi8(value, _mm256_set1_epi8(-33)),
      _mm256_cmpgt_epi8(_mm256_set1_epi8(-16), value));
  const __m256i lead4 = _mm256_and_si256(
      _mm256_cmpgt_epi8(value, _mm256_set1_epi8(-17)),
      _mm256_cmpgt_epi8(_mm256_set1_epi8(-11), value));

  const uint32_t continuation_bits =
      static_cast<uint32_t>(_mm256_movemask_epi8(continuation));
  const uint32_t lead2_bits =
      static_cast<uint32_t>(_mm256_movemask_epi8(lead2));
  const uint32_t lead3_bits =
      static_cast<uint32_t>(_mm256_movemask_epi8(lead3));
  const uint32_t lead4_bits =
      static_cast<uint32_t>(_mm256_movemask_epi8(lead4));

  const __m256i recognized = _mm256_or_si256(
      _mm256_or_si256(continuation, lead2),
      _mm256_or_si256(lead3, lead4));
  const __m256i unrecognized_high =
      _mm256_andnot_si256(recognized, high_bytes);
  if (!_mm256_testz_si256(unrecognized_high, unrecognized_high)) {
    return false;
  }

  const uint32_t expected =
      ((lead2_bits | lead3_bits | lead4_bits) << 1) |
      ((lead3_bits | lead4_bits) << 2) | (lead4_bits << 3) | *carry;
  if (expected != continuation_bits) {
    return false;
  }

  const __m256i special = _mm256_or_si256(
      _mm256_or_si256(
          _mm256_cmpeq_epi8(value, _mm256_set1_epi8(-32)),
          _mm256_cmpeq_epi8(value, _mm256_set1_epi8(-19))),
      _mm256_or_si256(
          _mm256_cmpeq_epi8(value, _mm256_set1_epi8(-16)),
          _mm256_cmpeq_epi8(value, _mm256_set1_epi8(-12))));
  uint32_t special_bits =
      static_cast<uint32_t>(_mm256_movemask_epi8(special));
  while (special_bits != 0) {
    const unsigned int lane =
        static_cast<unsigned int>(__builtin_ctz(special_bits));
    const size_t position = offset + lane;
    if (position + 1 < length) {
      const unsigned char lead = bytes[position];
      const unsigned char second = bytes[position + 1];
      if ((lead == 0xE0 && second < 0xA0) ||
          (lead == 0xED && second >= 0xA0) ||
          (lead == 0xF0 && second < 0x90) ||
          (lead == 0xF4 && second > 0x8F)) {
        return false;
      }
    }
    special_bits &= special_bits - 1;
  }

  uint32_t next_carry = 0;
  if ((lead2_bits & 0x80000000u) != 0) {
    next_carry |= 1u;
  }
  if ((lead3_bits & 0x40000000u) != 0) {
    next_carry |= 1u;
  }
  if ((lead3_bits & 0x80000000u) != 0) {
    next_carry |= 3u;
  }
  if ((lead4_bits & 0x20000000u) != 0) {
    next_carry |= 1u;
  }
  if ((lead4_bits & 0x40000000u) != 0) {
    next_carry |= 3u;
  }
  if ((lead4_bits & 0x80000000u) != 0) {
    next_carry |= 7u;
  }
  *carry = next_carry;
  return true;
}

static __attribute__((target("avx2"))) bool validate_utf8_avx2(
    const unsigned char *bytes, size_t length) {
  size_t index = 0;
  uint32_t carry = 0;

  // Test four complete vectors per loop iteration while passing boundary carry.
  while (length - index >= 128) {
    if (!validate_avx2_block(bytes, index, length, &carry) ||
        !validate_avx2_block(bytes, index + 32, length, &carry) ||
        !validate_avx2_block(bytes, index + 64, length, &carry) ||
        !validate_avx2_block(bytes, index + 96, length, &carry)) {
      return false;
    }
    index += 128;
  }
  while (length - index >= 32) {
    if (!validate_avx2_block(bytes, index, length, &carry)) {
      return false;
    }
    index += 32;
  }

  // Revalidate the final code point from its lead, including any block carry.
  size_t suffix_start = index;
  if (index != 0) {
    size_t position = index;
    unsigned int trailing_continuations = 0;
    while (position > 0 && trailing_continuations < 3 &&
           (bytes[position - 1] & 0xC0) == 0x80) {
      --position;
      ++trailing_continuations;
    }
    if (position > 0 && bytes[position - 1] >= 0xC0) {
      --position;
    }
    suffix_start = position;
  }
  return validate_utf8_scalar(bytes + suffix_start, length - suffix_start);
}
#endif

static bool validate_utf8(const char *input, size_t length) {
  if (length == 0) {
    return true;
  }
  const unsigned char *bytes = reinterpret_cast<const unsigned char *>(input);
#if (defined(__GNUC__) || defined(__clang__)) && (defined(__x86_64__) || defined(__i386__))
  __builtin_cpu_init();
  if (__builtin_cpu_supports("avx2")) {
    return validate_utf8_avx2(bytes, length);
  }
#endif
  return validate_utf8_scalar(bytes, length);
}

extern "C" void run(const void *input1, const void *input2, void *output,
                    int n, int parameter, int threads) {
  const uint32_t result =
      (n >= 0 && validate_utf8(static_cast<const char *>(input1),
                               static_cast<size_t>(n)))
          ? 1u
          : 0u;
  std::memcpy(output, &result, sizeof(result));
}
