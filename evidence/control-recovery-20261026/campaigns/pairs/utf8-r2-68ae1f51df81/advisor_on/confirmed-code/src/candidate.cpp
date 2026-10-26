#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <string.h>

#if defined(__AVX512BW__)
#include <immintrin.h>

static inline bool validate_avx512_block(__m512i current, __m512i previous,
                                         uint64_t valid_lanes,
                                         uint64_t incoming_pending,
                                         bool final_block,
                                         uint64_t *outgoing_pending) {
  const __m512i c7f = _mm512_set1_epi8((char)0x7f);
  const __m512i cc0 = _mm512_set1_epi8((char)0xc0);
  const __m512i cc2 = _mm512_set1_epi8((char)0xc2);
  const __m512i ce0 = _mm512_set1_epi8((char)0xe0);
  const __m512i cf0 = _mm512_set1_epi8((char)0xf0);
  const __m512i cf4 = _mm512_set1_epi8((char)0xf4);

  const __mmask64 non_ascii = _mm512_cmp_epu8_mask(current, c7f, _MM_CMPINT_GT);
  const __mmask64 ge_c0 = _mm512_cmp_epu8_mask(current, cc0, _MM_CMPINT_GE);
  const __mmask64 ge_e0 = _mm512_cmp_epu8_mask(current, ce0, _MM_CMPINT_GE);
  const __mmask64 ge_f0 = _mm512_cmp_epu8_mask(current, cf0, _MM_CMPINT_GE);
  const __mmask64 lt_c2 = _mm512_cmp_epu8_mask(current, cc2, _MM_CMPINT_LT);
  const __mmask64 gt_f4 = _mm512_cmp_epu8_mask(current, cf4, _MM_CMPINT_GT);

  const __mmask64 continuation = non_ascii & ~ge_c0;
  const __mmask64 lead2 = ge_c0 & ~ge_e0 & ~lt_c2;
  const __mmask64 lead3 = ge_e0 & ~ge_f0;
  const __mmask64 lead4 = ge_f0 & ~gt_f4;
  const __mmask64 bad_byte = non_ascii & ~(continuation | lead2 | lead3 | lead4);

  const __m512i ca0 = _mm512_set1_epi8((char)0xa0);
  const __m512i ca = _mm512_set1_epi8((char)0xa0);
  const __m512i c90 = _mm512_set1_epi8((char)0x90);
  const __m512i c8f = _mm512_set1_epi8((char)0x8f);
  const __mmask64 prev_e0 = _mm512_cmpeq_epi8_mask(previous, ce0);
  const __mmask64 prev_ed = _mm512_cmpeq_epi8_mask(previous, _mm512_set1_epi8((char)0xed));
  const __mmask64 prev_f0 = _mm512_cmpeq_epi8_mask(previous, cf0);
  const __mmask64 prev_f4 = _mm512_cmpeq_epi8_mask(previous, cf4);
  const __mmask64 restricted =
      (prev_e0 & _mm512_cmp_epu8_mask(current, ca0, _MM_CMPINT_LT)) |
      (prev_ed & _mm512_cmp_epu8_mask(current, ca, _MM_CMPINT_GE)) |
      (prev_f0 & _mm512_cmp_epu8_mask(current, c90, _MM_CMPINT_LT)) |
      (prev_f4 & _mm512_cmp_epu8_mask(current, c8f, _MM_CMPINT_GT));

  const uint64_t m2 = (uint64_t)lead2;
  const uint64_t m3 = (uint64_t)lead3;
  const uint64_t m4 = (uint64_t)lead4;
  const uint64_t required = (m2 << 1) | (m3 << 1) | (m3 << 2) |
                            (m4 << 1) | (m4 << 2) | (m4 << 3) |
                            incoming_pending;
  const uint64_t next_pending =
      (m2 >> 63) | (m3 >> 63) | (m4 >> 63) |
      ((m3 >> 62) & UINT64_C(3)) |
      ((m4 >> 62) & UINT64_C(3)) |
      ((m4 >> 61) & UINT64_C(7));
  const uint64_t valid_mask = valid_lanes;

  if (((uint64_t)bad_byte & valid_mask) != 0 ||
      ((uint64_t)restricted & valid_mask) != 0 ||
      (((uint64_t)continuation & valid_mask) != (required & valid_mask))) {
    return false;
  }
  if (final_block && ((required & ~valid_mask) != 0 || next_pending != 0)) {
    return false;
  }
  *outgoing_pending = next_pending;
  return true;
}

static inline bool validate_full_block(const unsigned char *bytes, size_t index,
                                       uint64_t *pending) {
  const __m512i current =
      _mm512_loadu_si512((const void *)(bytes + index));
  __m512i previous;
  if (index == 0) {
    alignas(64) unsigned char previous_bytes[64] = {};
    memcpy(previous_bytes + 1, bytes, 63);
    previous = _mm512_loadu_si512((const void *)previous_bytes);
  } else {
    previous = _mm512_loadu_si512((const void *)(bytes + index - 1));
  }
  return validate_avx512_block(current, previous, UINT64_MAX, *pending,
                               false, pending);
}

static bool validate_utf8_avx512(const char *input, size_t length) {
  const unsigned char *bytes = (const unsigned char *)input;
  size_t index = 0;
  uint64_t pending = 0;

  while (length - index >= 128) {
    if (!validate_full_block(bytes, index, &pending)) {
      return false;
    }
    index += 64;
    if (!validate_full_block(bytes, index, &pending)) {
      return false;
    }
    index += 64;
  }
  while (length - index >= 64) {
    if (!validate_full_block(bytes, index, &pending)) {
      return false;
    }
    index += 64;
  }
  if (index == length) {
    return pending == 0;
  }

  const size_t remaining = length - index;
  alignas(64) unsigned char current_bytes[64] = {};
  alignas(64) unsigned char previous_bytes[64] = {};
  memcpy(current_bytes, bytes + index, remaining);
  if (index != 0) {
    previous_bytes[0] = bytes[index - 1];
  }
  if (remaining > 1) {
    memcpy(previous_bytes + 1, bytes + index, remaining - 1);
  }
  const uint64_t valid_lanes = (UINT64_C(1) << remaining) - 1;
  return validate_avx512_block(
      _mm512_loadu_si512((const void *)current_bytes),
      _mm512_loadu_si512((const void *)previous_bytes), valid_lanes, pending,
      true, &pending);
}
#endif

static bool validate_utf8_scalar(const char *b, size_t length) {
  const unsigned char *bytes = (const unsigned char *)b;
  for (size_t index = 0;;) {
    unsigned char byte1;
    do {
      if (index >= length) {
        return true;
      }
      byte1 = bytes[index++];
    } while (byte1 < 0x80);
    if (byte1 < 0xe0) {
      if (index == length) {
        return false;
      }
      if (byte1 < 0xc2 || (bytes[index++] & 0xc0) != 0x80) {
        return false;
      }
    } else if (byte1 < 0xf0) {
      if (index + 1 >= length) {
        return false;
      }
      unsigned char byte2 = bytes[index++];
      if ((byte2 & 0xc0) != 0x80 ||
          (byte1 == 0xe0 && byte2 < 0xa0) ||
          (byte1 == 0xed && byte2 >= 0xa0) ||
          (bytes[index++] & 0xc0) != 0x80) {
        return false;
      }
    } else {
      if (index + 2 >= length) {
        return false;
      }
      int byte2 = bytes[index++];
      if ((byte2 & 0xc0) != 0x80 || byte1 > 0xf4 ||
          (byte1 == 0xf0 && byte2 < 0x90) ||
          (byte1 == 0xf4 && byte2 > 0x8f) ||
          (bytes[index++] & 0xc0) != 0x80 ||
          (bytes[index++] & 0xc0) != 0x80) {
        return false;
      }
    }
  }
}

static bool validate_utf8(const char *input, size_t length) {
#if defined(__AVX512BW__)
  return validate_utf8_avx512(input, length);
#else
  return validate_utf8_scalar(input, length);
#endif
}

extern "C" void run(const void *input1, const void *input2, void *output,
                    int n, int parameter, int threads) {
  (void)input2;
  (void)parameter;
  (void)threads;
  const bool valid = n >= 0 && validate_utf8((const char *)input1, (size_t)n);
  *(uint32_t *)output = valid ? 1u : 0u;
}
