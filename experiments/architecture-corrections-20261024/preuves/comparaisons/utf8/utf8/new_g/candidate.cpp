#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <cstdint>
#include <cstring>
#include <cmath>
#include <algorithm>
#include <omp.h>

#if defined(__GNUC__) && (defined(__x86_64__) || defined(__i386__))
#include <immintrin.h>
#define UTF8_HAS_AVX512_TARGET 1
#define UTF8_HAS_AVX2_TARGET 1
#else
#define UTF8_HAS_AVX512_TARGET 0
#define UTF8_HAS_AVX2_TARGET 0
#endif

static bool validate_utf8_scalar(const unsigned char *bytes, size_t length,
                                 size_t index, uint32_t pending) {
  while (pending != 0) {
    if (index >= length || (bytes[index++] & 0xC0u) != 0x80u) {
      return false;
    }
    pending >>= 1;
  }

  while (index < length) {
    const unsigned char byte1 = bytes[index++];
    if (byte1 < 0x80) {
      continue;
    }
    if (byte1 < 0xE0) {
      if (byte1 < 0xC2 || index >= length ||
          (bytes[index++] & 0xC0u) != 0x80u) {
        return false;
      }
    } else if (byte1 < 0xF0) {
      if (length - index < 2) {
        return false;
      }
      const unsigned char byte2 = bytes[index++];
      if ((byte2 & 0xC0u) != 0x80u ||
          (byte1 == 0xE0 && byte2 < 0xA0) ||
          (byte1 == 0xED && byte2 >= 0xA0) ||
          (bytes[index++] & 0xC0u) != 0x80u) {
        return false;
      }
    } else {
      if (length - index < 3) {
        return false;
      }
      const unsigned char byte2 = bytes[index++];
      if ((byte2 & 0xC0u) != 0x80u || byte1 > 0xF4 ||
          (byte1 == 0xF0 && byte2 < 0x90) ||
          (byte1 == 0xF4 && byte2 > 0x8F) ||
          (bytes[index++] & 0xC0u) != 0x80u ||
          (bytes[index++] & 0xC0u) != 0x80u) {
        return false;
      }
    }
  }
  return true;
}

#if UTF8_HAS_AVX2_TARGET
__attribute__((target("avx2"), always_inline))
static inline bool validate_utf8_avx2_block(const unsigned char *bytes,
                                            size_t offset,
                                            uint32_t *pending) {
  const __m256i zero = _mm256_setzero_si256();
  const __m256i one = _mm256_set1_epi8(1);
  const __m256i four = _mm256_set1_epi8(4);
  const __m256i mask_07 = _mm256_set1_epi8(7);
  const __m256i mask_1f = _mm256_set1_epi8(0x1F);
  const __m256i mask_20 = _mm256_set1_epi8(0x20);
  const __m256i mask_30 = _mm256_set1_epi8(0x30);
  const __m256i mask_80 = _mm256_set1_epi8(static_cast<char>(0x80));
  const __m256i mask_c0 = _mm256_set1_epi8(static_cast<char>(0xC0));
  const __m256i mask_e0 = _mm256_set1_epi8(static_cast<char>(0xE0));
  const __m256i mask_f0 = _mm256_set1_epi8(static_cast<char>(0xF0));
  const __m256i mask_f8 = _mm256_set1_epi8(static_cast<char>(0xF8));
  const __m256i mask_f4 = _mm256_set1_epi8(static_cast<char>(0xF4));

  const __m256i current = _mm256_loadu_si256(
      reinterpret_cast<const __m256i *>(bytes + offset));
  const __m256i next1 = _mm256_loadu_si256(
      reinterpret_cast<const __m256i *>(bytes + offset + 1));

  const __m256i ascii = _mm256_cmpeq_epi8(
      _mm256_and_si256(current, mask_80), zero);
  const __m256i continuation = _mm256_cmpeq_epi8(
      _mm256_and_si256(current, mask_c0), mask_80);
  const __m256i lead2 = _mm256_and_si256(
      _mm256_cmpeq_epi8(_mm256_and_si256(current, mask_e0), mask_c0),
      _mm256_cmpgt_epi8(_mm256_and_si256(current, mask_1f), one));
  const __m256i lead3 = _mm256_cmpeq_epi8(
      _mm256_and_si256(current, mask_f0), mask_e0);
  const __m256i high4 = _mm256_cmpeq_epi8(
      _mm256_and_si256(current, mask_f8), mask_f0);
  const __m256i invalid4_low = _mm256_cmpgt_epi8(
      _mm256_and_si256(current, mask_07), four);
  const __m256i lead4 = _mm256_andnot_si256(invalid4_low, high4);
  const __m256i valid = _mm256_or_si256(
      _mm256_or_si256(ascii, continuation),
      _mm256_or_si256(lead2, _mm256_or_si256(lead3, lead4)));

  if (_mm256_movemask_epi8(valid) != -1) {
    return false;
  }

  const __m256i e0 = _mm256_cmpeq_epi8(
      current, _mm256_set1_epi8(static_cast<char>(0xE0)));
  const __m256i ed = _mm256_cmpeq_epi8(
      current, _mm256_set1_epi8(static_cast<char>(0xED)));
  const __m256i f0 = _mm256_cmpeq_epi8(
      current, _mm256_set1_epi8(static_cast<char>(0xF0)));
  const __m256i f4 = _mm256_cmpeq_epi8(current, mask_f4);

  const __m256i second_bit5 = _mm256_and_si256(next1, mask_20);
  const __m256i bad_e0 = _mm256_and_si256(
      e0, _mm256_cmpeq_epi8(second_bit5, zero));
  const __m256i bad_ed = _mm256_and_si256(
      ed, _mm256_cmpeq_epi8(second_bit5, mask_20));
  const __m256i bad_f0 = _mm256_and_si256(
      f0, _mm256_cmpeq_epi8(_mm256_and_si256(next1, mask_f0), mask_80));
  const __m256i bad_f4 = _mm256_andnot_si256(
      _mm256_cmpeq_epi8(_mm256_and_si256(next1, mask_30), zero), f4);
  const __m256i bad_second = _mm256_or_si256(
      _mm256_or_si256(bad_e0, bad_ed), _mm256_or_si256(bad_f0, bad_f4));
  if (_mm256_movemask_epi8(bad_second) != 0) {
    return false;
  }

  const uint32_t lead2_bits =
      static_cast<uint32_t>(_mm256_movemask_epi8(lead2));
  const uint32_t lead3_bits =
      static_cast<uint32_t>(_mm256_movemask_epi8(lead3));
  const uint32_t lead4_bits =
      static_cast<uint32_t>(_mm256_movemask_epi8(lead4));
  const uint64_t expected =
      (static_cast<uint64_t>(lead2_bits) << 1) |
      (static_cast<uint64_t>(lead3_bits) << 1) |
      (static_cast<uint64_t>(lead3_bits) << 2) |
      (static_cast<uint64_t>(lead4_bits) << 1) |
      (static_cast<uint64_t>(lead4_bits) << 2) |
      (static_cast<uint64_t>(lead4_bits) << 3);
  const uint32_t continuation_bits =
      static_cast<uint32_t>(_mm256_movemask_epi8(continuation));
  if (continuation_bits !=
      (static_cast<uint32_t>(expected) | *pending)) {
    return false;
  }

  *pending = static_cast<uint32_t>(expected >> 32);
  return true;
}

__attribute__((target("avx2")))
static bool validate_utf8_avx2(const unsigned char *bytes, size_t length) {
  size_t offset = 0;
  uint32_t pending = 0;

  while (length - offset >= 33) {
    if (!validate_utf8_avx2_block(bytes, offset, &pending)) {
      return false;
    }
    offset += 32;
  }

  return validate_utf8_scalar(bytes, length, offset, pending);
}
#endif

#if UTF8_HAS_AVX512_TARGET
__attribute__((target("avx512f,avx512bw"), always_inline))
static inline bool validate_utf8_avx512_block(const unsigned char *bytes,
                                               uint64_t &pending) {
  const __m512i current = _mm512_loadu_si512(
      reinterpret_cast<const void *>(bytes));
  const __m512i next1 = _mm512_loadu_si512(
      reinterpret_cast<const void *>(bytes + 1));
  const __m512i zero = _mm512_setzero_si512();
  const __m512i one = _mm512_set1_epi8(1);
  const __m512i four = _mm512_set1_epi8(4);
  const __m512i mask_07 = _mm512_set1_epi8(7);
  const __m512i mask_1f = _mm512_set1_epi8(0x1F);
  const __m512i mask_20 = _mm512_set1_epi8(0x20);
  const __m512i mask_30 = _mm512_set1_epi8(0x30);
  const __m512i mask_80 = _mm512_set1_epi8(static_cast<char>(0x80));
  const __m512i mask_c0 = _mm512_set1_epi8(static_cast<char>(0xC0));
  const __m512i mask_e0 = _mm512_set1_epi8(static_cast<char>(0xE0));
  const __m512i mask_f0 = _mm512_set1_epi8(static_cast<char>(0xF0));
  const __m512i mask_f4 = _mm512_set1_epi8(static_cast<char>(0xF4));
  const __m512i mask_f8 = _mm512_set1_epi8(static_cast<char>(0xF8));

  const __mmask64 ascii = _mm512_cmpeq_epi8_mask(
      _mm512_and_si512(current, mask_80), zero);
  const __mmask64 continuation = _mm512_cmpeq_epi8_mask(
      _mm512_and_si512(current, mask_c0), mask_80);
  const __mmask64 lead2 =
      _mm512_cmpeq_epi8_mask(_mm512_and_si512(current, mask_e0), mask_c0) &
      _mm512_cmpgt_epi8_mask(_mm512_and_si512(current, mask_1f), one);
  const __mmask64 lead3 = _mm512_cmpeq_epi8_mask(
      _mm512_and_si512(current, mask_f0), mask_e0);
  const __mmask64 high4 = _mm512_cmpeq_epi8_mask(
      _mm512_and_si512(current, mask_f8), mask_f0);
  const __mmask64 invalid4_low = _mm512_cmpgt_epi8_mask(
      _mm512_and_si512(current, mask_07), four);
  const __mmask64 lead4 = high4 & ~invalid4_low;
  const __mmask64 valid = ascii | continuation | lead2 | lead3 | lead4;

  if (valid != static_cast<__mmask64>(-1)) {
    return false;
  }

  const __mmask64 e0 = _mm512_cmpeq_epi8_mask(
      current, _mm512_set1_epi8(static_cast<char>(0xE0)));
  const __mmask64 ed = _mm512_cmpeq_epi8_mask(
      current, _mm512_set1_epi8(static_cast<char>(0xED)));
  const __mmask64 f0 = _mm512_cmpeq_epi8_mask(
      current, _mm512_set1_epi8(static_cast<char>(0xF0)));
  const __mmask64 f4 = _mm512_cmpeq_epi8_mask(current, mask_f4);

  const __mmask64 bad_e0 = e0 & _mm512_cmpeq_epi8_mask(
      _mm512_and_si512(next1, mask_20), zero);
  const __mmask64 bad_ed = ed & _mm512_cmpeq_epi8_mask(
      _mm512_and_si512(next1, mask_20), mask_20);
  const __mmask64 bad_f0 = f0 & _mm512_cmpeq_epi8_mask(
      _mm512_and_si512(next1, mask_f0), mask_80);
  const __mmask64 bad_f4 = f4 & ~_mm512_cmpeq_epi8_mask(
      _mm512_and_si512(next1, mask_30), zero);
  if ((bad_e0 | bad_ed | bad_f0 | bad_f4) != 0) {
    return false;
  }

  const uint64_t lead2_bits = static_cast<uint64_t>(lead2);
  const uint64_t lead3_bits = static_cast<uint64_t>(lead3);
  const uint64_t lead4_bits = static_cast<uint64_t>(lead4);
  const uint64_t expected_low =
      (lead2_bits << 1) |
      (lead3_bits << 1) | (lead3_bits << 2) |
      (lead4_bits << 1) | (lead4_bits << 2) | (lead4_bits << 3);
  const uint64_t expected_next =
      (lead2_bits >> 63) |
      (lead3_bits >> 63) | (lead3_bits >> 62) |
      (lead4_bits >> 63) | (lead4_bits >> 62) | (lead4_bits >> 61);
  const uint64_t continuation_bits = static_cast<uint64_t>(continuation);
  if (continuation_bits != (expected_low | pending)) {
    return false;
  }

  pending = expected_next;
  return true;
}

__attribute__((target("avx512f,avx512bw")))
static bool validate_utf8_avx512(const unsigned char *bytes, size_t length) {
  size_t offset = 0;
  uint64_t pending = 0;

  while (length - offset >= 129) {
    if (!validate_utf8_avx512_block(bytes + offset, pending) ||
        !validate_utf8_avx512_block(bytes + offset + 64, pending)) {
      return false;
    }
    offset += 128;
  }

  while (length - offset >= 65) {
    if (!validate_utf8_avx512_block(bytes + offset, pending)) {
      return false;
    }
    offset += 64;
  }

  return validate_utf8_scalar(bytes, length, offset,
                              static_cast<uint32_t>(pending));
}
#endif

static bool validate_utf8(const char *input, size_t length) {
  const unsigned char *bytes = reinterpret_cast<const unsigned char *>(input);
#if UTF8_HAS_AVX512_TARGET
  if (length >= 65) {
    return validate_utf8_avx512(bytes, length);
  }
#endif
#if UTF8_HAS_AVX2_TARGET
  if (length >= 33) {
    return validate_utf8_avx2(bytes, length);
  }
#endif
  return validate_utf8_scalar(bytes, length, 0, 0);
}

extern "C" void run(const void *input1, const void *input2, void *output,
                    int n, int parameter, int threads) {
  *(uint32_t *)output = validate_utf8((const char *)input1, n);
}
