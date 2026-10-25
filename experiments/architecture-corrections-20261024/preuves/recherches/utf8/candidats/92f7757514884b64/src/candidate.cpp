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
#define UTF8_HAS_AVX512BW_TARGET 1
#else
#define UTF8_HAS_AVX512BW_TARGET 0
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

#if UTF8_HAS_AVX512BW_TARGET
__attribute__((target("avx512f,avx512bw"), always_inline))
static inline bool validate_utf8_avx512_block(__m512i current,
                                             __m512i next1,
                                             uint32_t &pending) {
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

  if ((ascii | continuation | lead2 | lead3 | lead4) !=
      ~static_cast<__mmask64>(0)) {
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
  const uint64_t expected =
      (lead2_bits << 1) |
      (lead3_bits << 1) | (lead3_bits << 2) |
      (lead4_bits << 1) | (lead4_bits << 2) | (lead4_bits << 3);
  const uint64_t continuation_bits = static_cast<uint64_t>(continuation);
  if (continuation_bits != (expected | static_cast<uint64_t>(pending))) {
    return false;
  }

  // Carry the expected continuation positions beyond lane 63 into the next block.
  pending = static_cast<uint32_t>(
      ((lead2_bits >> 63) & 1u) |
      ((lead3_bits >> 62) & 1u) |
      (((lead3_bits >> 63) & 1u) * 3u) |
      ((lead4_bits >> 61) & 1u) |
      (((lead4_bits >> 62) & 1u) * 3u) |
      (((lead4_bits >> 63) & 1u) * 7u));
  return true;
}

__attribute__((target("avx512f,avx512bw")))
static bool validate_utf8_avx512(const unsigned char *bytes, size_t length) {
  size_t offset = 0;
  uint32_t pending = 0;
  __m512i current = _mm512_loadu_si512(
      reinterpret_cast<const void *>(bytes));
  const __m512i next_dword_indices = _mm512_setr_epi32(
      4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19);

  // Reuse the next 64-byte block to build the shifted bytes for this block.
  while (length - offset >= 128) {
    const __m512i following = _mm512_loadu_si512(
        reinterpret_cast<const void *>(bytes + offset + 64));
    const __m512i following_lanes = _mm512_permutex2var_epi32(
        current, next_dword_indices, following);
    const __m512i next1 = _mm512_alignr_epi8(following_lanes, current, 1);
    if (!validate_utf8_avx512_block(current, next1, pending)) {
      return false;
    }
    offset += 64;
    current = following;
  }

  // A final overlapping load is safe only when all 65 bytes are present.
  if (length - offset >= 65) {
    const __m512i next1 = _mm512_loadu_si512(
        reinterpret_cast<const void *>(bytes + offset + 1));
    if (!validate_utf8_avx512_block(current, next1, pending)) {
      return false;
    }
    offset += 64;
  }

  return validate_utf8_scalar(bytes, length, offset, pending);
}
#endif

static bool validate_utf8(const char *input, size_t length) {
  const unsigned char *bytes = reinterpret_cast<const unsigned char *>(input);
#if UTF8_HAS_AVX512BW_TARGET
  if (length >= 65) {
    return validate_utf8_avx512(bytes, length);
  }
#endif
  return validate_utf8_scalar(bytes, length, 0, 0);
}

extern "C" void run(const void *input1, const void *input2, void *output,
                    int n, int parameter, int threads) {
  *(uint32_t *)output = validate_utf8((const char *)input1, n);
}
