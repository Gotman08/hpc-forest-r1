#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#if (defined(__GNUC__) || defined(__clang__)) && (defined(__x86_64__) || defined(__i386__))
#include <immintrin.h>
#define UTF8_HAS_AVX2_TARGET 1
#endif
#include <cstdint>
#include <cstring>
#include <cmath>
#include <algorithm>
#include <omp.h>

static bool validate_utf8_scalar_from(const unsigned char *bytes, size_t length,
                                      size_t index) {
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

#if defined(UTF8_HAS_AVX2_TARGET)
__attribute__((target("avx2")))
static bool validate_utf8_avx2(const unsigned char *bytes, size_t length) {
  size_t index = 0;
  uint32_t pending = 0;
  const __m256i zero = _mm256_setzero_si256();
  const __m256i all_ones = _mm256_set1_epi8(static_cast<char>(-1));
  const __m256i minus_65 = _mm256_set1_epi8(static_cast<char>(-65));
  const __m256i minus_63 = _mm256_set1_epi8(static_cast<char>(-63));
  const __m256i minus_33 = _mm256_set1_epi8(static_cast<char>(-33));
  const __m256i minus_32 = _mm256_set1_epi8(static_cast<char>(-32));
  const __m256i minus_17 = _mm256_set1_epi8(static_cast<char>(-17));
  const __m256i minus_16 = _mm256_set1_epi8(static_cast<char>(-16));
  const __m256i minus_12 = _mm256_set1_epi8(static_cast<char>(-12));
  const __m256i minus_11 = _mm256_set1_epi8(static_cast<char>(-11));

  while (length - index >= 32) {
    const __m256i value = _mm256_loadu_si256(
        reinterpret_cast<const __m256i *>(bytes + index));

    if (pending == 0 && _mm256_movemask_epi8(value) == 0) {
      index += 32;
      continue;
    }

    const __m256i high_bytes = _mm256_cmpgt_epi8(zero, value);
    const __m256i above_bf = _mm256_cmpgt_epi8(value, minus_65);
    const __m256i continuation =
        _mm256_and_si256(high_bytes,
                         _mm256_andnot_si256(above_bf, all_ones));
    const __m256i ascii = _mm256_andnot_si256(high_bytes, all_ones);
    const __m256i lead2 = _mm256_and_si256(
        _mm256_cmpgt_epi8(value, minus_63),
        _mm256_cmpgt_epi8(minus_32, value));
    const __m256i lead3 = _mm256_and_si256(
        _mm256_cmpgt_epi8(value, minus_33),
        _mm256_cmpgt_epi8(minus_16, value));
    const __m256i lead4 = _mm256_and_si256(
        _mm256_cmpgt_epi8(value, minus_17),
        _mm256_cmpgt_epi8(minus_11, value));
    const __m256i valid = _mm256_or_si256(
        _mm256_or_si256(ascii, continuation),
        _mm256_or_si256(_mm256_or_si256(lead2, lead3), lead4));

    const uint32_t valid_bits =
        static_cast<uint32_t>(_mm256_movemask_epi8(valid));
    if (valid_bits != 0xffffffffu) {
      return false;
    }

    const __m256i restricted = _mm256_or_si256(
        _mm256_or_si256(
            _mm256_cmpeq_epi8(value, _mm256_set1_epi8(static_cast<char>(0xE0))),
            _mm256_cmpeq_epi8(value, _mm256_set1_epi8(static_cast<char>(0xED)))),
        _mm256_or_si256(
            _mm256_cmpeq_epi8(value, _mm256_set1_epi8(static_cast<char>(0xF0))),
            _mm256_cmpeq_epi8(value, _mm256_set1_epi8(static_cast<char>(0xF4)))));
    uint32_t restricted_bits =
        static_cast<uint32_t>(_mm256_movemask_epi8(restricted));
    while (restricted_bits != 0) {
      const unsigned int lane =
          static_cast<unsigned int>(__builtin_ctz(restricted_bits));
      restricted_bits &= restricted_bits - 1;
      const size_t offset = index + lane;
      if (offset + 1 >= length) {
        return false;
      }
      const unsigned char lead = bytes[offset];
      const unsigned char second = bytes[offset + 1];
      if ((lead == 0xE0 && second < 0xA0) ||
          (lead == 0xED && second >= 0xA0) ||
          (lead == 0xF0 && second < 0x90) ||
          (lead == 0xF4 && second > 0x8F)) {
        return false;
      }
    }

    const uint32_t lead2_bits =
        static_cast<uint32_t>(_mm256_movemask_epi8(lead2));
    const uint32_t lead3_bits =
        static_cast<uint32_t>(_mm256_movemask_epi8(lead3));
    const uint32_t lead4_bits =
        static_cast<uint32_t>(_mm256_movemask_epi8(lead4));
    const uint32_t continuation_bits =
        static_cast<uint32_t>(_mm256_movemask_epi8(continuation));
    const uint64_t expected_wide =
        (static_cast<uint64_t>(lead2_bits) << 1) |
        (static_cast<uint64_t>(lead3_bits) << 1) |
        (static_cast<uint64_t>(lead3_bits) << 2) |
        (static_cast<uint64_t>(lead4_bits) << 1) |
        (static_cast<uint64_t>(lead4_bits) << 2) |
        (static_cast<uint64_t>(lead4_bits) << 3) |
        static_cast<uint64_t>(pending);
    if (static_cast<uint32_t>(expected_wide) != continuation_bits) {
      return false;
    }
    pending = static_cast<uint32_t>(expected_wide >> 32);
    index += 32;
  }

  while (pending != 0) {
    if ((pending & 1u) == 0 || index >= length ||
        (bytes[index] & 0xC0) != 0x80) {
      return false;
    }
    ++index;
    pending >>= 1;
  }
  return validate_utf8_scalar_from(bytes, length, index);
}
#endif

static bool validate_utf8(const char *b, size_t length) {
  const unsigned char *bytes = reinterpret_cast<const unsigned char *>(b);
#if defined(UTF8_HAS_AVX2_TARGET)
  if (length >= 32 && __builtin_cpu_supports("avx2")) {
    return validate_utf8_avx2(bytes, length);
  }
#endif
  return validate_utf8_scalar_from(bytes, length, 0);
}

extern "C" void run(const void *input1, const void *input2, void *output,
                     int n, int parameter, int threads) {
  *static_cast<uint32_t *>(output) =
      validate_utf8(static_cast<const char *>(input1), static_cast<size_t>(n));
}
