#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#if (defined(__i386__) || defined(__x86_64__)) && \
    (defined(__GNUC__) || defined(__clang__))
#define UTF8_HAVE_X86_SIMD 1
#include <immintrin.h>
#else
#define UTF8_HAVE_X86_SIMD 0
#endif

/* Reference scalar validator, used for short inputs and non-x86 builds. */
static bool validate_utf8_reference(const char *buffer, size_t length) {
  const unsigned char *bytes = (const unsigned char *)buffer;
  for (size_t index = 0;;) {
    unsigned char byte1;

    do {
      if (index >= length) {
        return true;
      }
      byte1 = bytes[index++];
    } while (byte1 < 0x80);

    if (byte1 < 0xE0) {
      if (index == length) {
        return false;
      }
      if (byte1 < 0xC2 || (bytes[index++] & 0xC0) != 0x80) {
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

/* Validate the final partial vector, including continuations carried in. */
static bool validate_utf8_scalar_tail(const unsigned char *bytes,
                                      size_t length, size_t index,
                                      uint32_t carry) {
  unsigned int pending = 0;
  while (carry & 1u) {
    ++pending;
    carry >>= 1;
  }
  if (carry != 0) {
    return false;
  }

  while (index < length) {
    unsigned char first = bytes[index];
    if (pending != 0) {
      if ((first & 0xC0) != 0x80) {
        return false;
      }
      --pending;
      ++index;
      continue;
    }

    if (first < 0x80) {
      ++index;
    } else if (first <= 0xDF) {
      if (first < 0xC2 || length - index < 2 ||
          (bytes[index + 1] & 0xC0) != 0x80) {
        return false;
      }
      index += 2;
    } else if (first <= 0xEF) {
      if (length - index < 3) {
        return false;
      }
      unsigned char second = bytes[index + 1];
      if ((second & 0xC0) != 0x80 ||
          (first == 0xE0 && second < 0xA0) ||
          (first == 0xED && second > 0x9F) ||
          (bytes[index + 2] & 0xC0) != 0x80) {
        return false;
      }
      index += 3;
    } else {
      if (first > 0xF4 || length - index < 4) {
        return false;
      }
      unsigned char second = bytes[index + 1];
      if ((second & 0xC0) != 0x80 ||
          (first == 0xF0 && second < 0x90) ||
          (first == 0xF4 && second > 0x8F) ||
          (bytes[index + 2] & 0xC0) != 0x80 ||
          (bytes[index + 3] & 0xC0) != 0x80) {
        return false;
      }
      index += 4;
    }
  }
  return pending == 0;
}

#if UTF8_HAVE_X86_SIMD
static bool validate_restricted_tail(const unsigned char *bytes,
                                     size_t length, size_t index,
                                     uint32_t candidates) {
  while (candidates != 0) {
    unsigned int lane = (unsigned int)__builtin_ctz(candidates);
    candidates &= candidates - 1;
    size_t position = index + lane;
    if (position + 1 >= length) {
      return false;
    }
    unsigned char first = bytes[position];
    unsigned char second = bytes[position + 1];
    if ((first == 0xE0 && second < 0xA0) ||
        (first == 0xED && second > 0x9F) ||
        (first == 0xF0 && second < 0x90) ||
        (first == 0xF4 && second > 0x8F)) {
      return false;
    }
  }
  return true;
}

static bool __attribute__((target("avx2")))
validate_utf8_avx2(const unsigned char *bytes, size_t length) {
  size_t index = 0;
  uint32_t carry = 0;
  const __m256i zero = _mm256_setzero_si256();
  const __m256i c20 = _mm256_set1_epi8((char)0x20);
  const __m256i c30 = _mm256_set1_epi8((char)0x30);

  while (length - index >= 32) {
    __m256i value = _mm256_loadu_si256((const __m256i *)(bytes + index));
    const __m256i mask_c0 = _mm256_set1_epi8((char)0xC0);
    const __m256i mask_e0 = _mm256_set1_epi8((char)0xE0);
    const __m256i mask_fe = _mm256_set1_epi8((char)0xFE);
    const __m256i mask_f0 = _mm256_set1_epi8((char)0xF0);
    const __m256i mask_fc = _mm256_set1_epi8((char)0xFC);
    const __m256i value_80 = _mm256_set1_epi8((char)0x80);
    const __m256i value_c0 = _mm256_set1_epi8((char)0xC0);
    const __m256i value_e0 = _mm256_set1_epi8((char)0xE0);
    const __m256i value_f0 = _mm256_set1_epi8((char)0xF0);
    const __m256i value_f4 = _mm256_set1_epi8((char)0xF4);

    __m256i continuation_vec = _mm256_cmpeq_epi8(
        _mm256_and_si256(value, mask_c0), value_80);
    __m256i lead2_candidate = _mm256_cmpeq_epi8(
        _mm256_and_si256(value, mask_e0), value_c0);
    __m256i lead2_invalid = _mm256_cmpeq_epi8(
        _mm256_and_si256(value, mask_fe), value_c0);
    __m256i lead2_vec = _mm256_andnot_si256(lead2_invalid, lead2_candidate);
    __m256i lead3_vec = _mm256_cmpeq_epi8(
        _mm256_and_si256(value, mask_f0), value_e0);
    __m256i lead4_vec = _mm256_or_si256(
        _mm256_cmpeq_epi8(_mm256_and_si256(value, mask_fc), value_f0),
        _mm256_cmpeq_epi8(value, value_f4));

    uint32_t continuation = (uint32_t)_mm256_movemask_epi8(continuation_vec);
    uint32_t lead2 = (uint32_t)_mm256_movemask_epi8(lead2_vec);
    uint32_t lead3 = (uint32_t)_mm256_movemask_epi8(lead3_vec);
    uint32_t lead4 = (uint32_t)_mm256_movemask_epi8(lead4_vec);
    uint32_t high = (uint32_t)_mm256_movemask_epi8(value);
    if ((high & ~(continuation | lead2 | lead3 | lead4)) != 0) {
      return false;
    }

    uint64_t expected =
        ((uint64_t)(lead2 | lead3 | lead4) << 1) |
        ((uint64_t)(lead3 | lead4) << 2) | ((uint64_t)lead4 << 3);
    uint32_t current_expected = (uint32_t)expected | carry;
    if (continuation != current_expected) {
      return false;
    }
    carry = (uint32_t)(expected >> 32);

    if (length - index > 32) {
      __m256i next = _mm256_loadu_si256((const __m256i *)(bytes + index + 1));
      __m256i e0 = _mm256_cmpeq_epi8(value, value_e0);
      __m256i ed = _mm256_cmpeq_epi8(value, _mm256_set1_epi8((char)0xED));
      __m256i f0 = _mm256_cmpeq_epi8(value, value_f0);
      __m256i f4 = _mm256_cmpeq_epi8(value, value_f4);
      __m256i second20 = _mm256_and_si256(next, c20);
      __m256i second30 = _mm256_and_si256(next, c30);
      __m256i bad = _mm256_or_si256(
          _mm256_or_si256(
              _mm256_and_si256(e0, _mm256_cmpeq_epi8(second20, zero)),
              _mm256_and_si256(ed, _mm256_cmpeq_epi8(second20, c20))),
          _mm256_or_si256(
              _mm256_and_si256(f0, _mm256_cmpeq_epi8(second30, zero)),
              _mm256_andnot_si256(_mm256_cmpeq_epi8(second30, zero), f4)));
      if (_mm256_movemask_epi8(bad) != 0) {
        return false;
      }
    } else {
      uint32_t restricted =
          (uint32_t)_mm256_movemask_epi8(_mm256_cmpeq_epi8(value, value_e0)) |
          (uint32_t)_mm256_movemask_epi8(
              _mm256_cmpeq_epi8(value, _mm256_set1_epi8((char)0xED))) |
          (uint32_t)_mm256_movemask_epi8(_mm256_cmpeq_epi8(value, value_f0)) |
          (uint32_t)_mm256_movemask_epi8(_mm256_cmpeq_epi8(value, value_f4));
      if (!validate_restricted_tail(bytes, length, index, restricted)) {
        return false;
      }
    }
    index += 32;
  }

  return validate_utf8_scalar_tail(bytes, length, index, carry);
}
#endif

static bool validate_utf8(const char *buffer, size_t length) {
  const unsigned char *bytes = (const unsigned char *)buffer;
#if UTF8_HAVE_X86_SIMD
  /* The campaign target is a fixed EPYC 9654, which supports AVX2. */
  if (length >= 64) {
    return validate_utf8_avx2(bytes, length);
  }
#endif
  return validate_utf8_reference(buffer, length);
}

extern "C" void run(const void *input1, const void *input2, void *output,
                     int n, int parameter, int threads) {
  bool valid = n >= 0 && validate_utf8((const char *)input1, (size_t)n);
  *(uint32_t *)output = valid ? 1u : 0u;
}
