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
#else
#define UTF8_HAS_AVX512_TARGET 0
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

#if UTF8_HAS_AVX512_TARGET
__attribute__((target("avx512f,avx512bw")))
static bool validate_utf8_avx512(const unsigned char *bytes, size_t length) {
  size_t offset = 0;
  uint32_t pending = 0;
  const __m512i zero = _mm512_setzero_si512();
  const __m512i mask_80 = _mm512_set1_epi8(static_cast<char>(0x80));
  const __m512i mask_c0 = _mm512_set1_epi8(static_cast<char>(0xC0));
  const __m512i mask_f0 = _mm512_set1_epi8(static_cast<char>(0xF0));
  const __m512i mask_f8 = _mm512_set1_epi8(static_cast<char>(0xF8));
  const __m512i value_80 = _mm512_set1_epi8(static_cast<char>(0x80));
  const __m512i value_c2 = _mm512_set1_epi8(static_cast<char>(0xC2));
  const __m512i value_e0 = _mm512_set1_epi8(static_cast<char>(0xE0));
  const __m512i value_f0 = _mm512_set1_epi8(static_cast<char>(0xF0));
  const __m512i value_f5 = _mm512_set1_epi8(static_cast<char>(0xF5));
  const __m512i value_a0 = _mm512_set1_epi8(static_cast<char>(0xA0));
  const __m512i value_90 = _mm512_set1_epi8(static_cast<char>(0x90));
  const __m512i value_8f = _mm512_set1_epi8(static_cast<char>(0x8F));
  const __m512i value_e0_byte = _mm512_set1_epi8(static_cast<char>(0xE0));
  const __m512i value_ed_byte = _mm512_set1_epi8(static_cast<char>(0xED));
  const __m512i value_f4_byte = _mm512_set1_epi8(static_cast<char>(0xF4));

  // The shifted load reads through offset + 64, so 65 remaining bytes are
  // required. The final at-most-64 bytes are checked by the scalar validator.
  while (length - offset >= 65) {
    const __m512i current = _mm512_loadu_si512(
        reinterpret_cast<const void *>(bytes + offset));
    const __mmask64 ascii_only = _mm512_cmp_epu8_mask(
        current, value_80, _MM_CMPINT_LT);

    // ASCII blocks need no look-ahead or continuation bookkeeping.
    if (pending == 0 && ascii_only == static_cast<__mmask64>(UINT64_MAX)) {
      offset += 64;
      continue;
    }

    const __m512i next1 = _mm512_loadu_si512(
        reinterpret_cast<const void *>(bytes + offset + 1));

    const __mmask64 ascii = ascii_only;
    const __mmask64 continuation = _mm512_cmpeq_epi8_mask(
        _mm512_and_si512(current, mask_c0), mask_80);
    const __mmask64 lead2 =
        _mm512_cmp_epu8_mask(current, value_c2, _MM_CMPINT_GE) &
        _mm512_cmp_epu8_mask(current, value_e0, _MM_CMPINT_LT);
    const __mmask64 lead3 = _mm512_cmpeq_epi8_mask(
        _mm512_and_si512(current, mask_f0), value_e0);
    const __mmask64 lead4 =
        _mm512_cmp_epu8_mask(current, value_f0, _MM_CMPINT_GE) &
        _mm512_cmp_epu8_mask(current, value_f5, _MM_CMPINT_LT);
    const __mmask64 valid = ascii | continuation | lead2 | lead3 | lead4;
    if (valid != static_cast<__mmask64>(UINT64_MAX)) {
      return false;
    }

    const __mmask64 lead_e0 =
        _mm512_cmpeq_epi8_mask(current, value_e0_byte);
    const __mmask64 lead_ed =
        _mm512_cmpeq_epi8_mask(current, value_ed_byte);
    const __mmask64 lead_f0 =
        _mm512_cmpeq_epi8_mask(current, value_f0);
    const __mmask64 lead_f4 =
        _mm512_cmpeq_epi8_mask(current, value_f4_byte);
    const __mmask64 bad_e0 =
        lead_e0 & _mm512_cmp_epu8_mask(next1, value_a0, _MM_CMPINT_LT);
    const __mmask64 bad_ed =
        lead_ed & _mm512_cmp_epu8_mask(next1, value_a0, _MM_CMPINT_GE);
    const __mmask64 bad_f0 =
        lead_f0 & _mm512_cmp_epu8_mask(next1, value_90, _MM_CMPINT_LT);
    const __mmask64 bad_f4 =
        lead_f4 & _mm512_cmp_epu8_mask(next1, value_8f, _MM_CMPINT_GT);
    if ((bad_e0 | bad_ed | bad_f0 | bad_f4) != 0) {
      return false;
    }

    const uint64_t lead2_bits = static_cast<uint64_t>(lead2);
    const uint64_t lead3_bits = static_cast<uint64_t>(lead3);
    const uint64_t lead4_bits = static_cast<uint64_t>(lead4);
    const uint64_t expected =
        (lead2_bits << 1) | (lead3_bits << 1) | (lead3_bits << 2) |
        (lead4_bits << 1) | (lead4_bits << 2) | (lead4_bits << 3);
    const uint64_t continuation_bits =
        static_cast<uint64_t>(continuation);
    if (continuation_bits != (expected | static_cast<uint64_t>(pending))) {
      return false;
    }

    const uint32_t pending0 = static_cast<uint32_t>(
        ((lead2_bits >> 63) & 1u) | ((lead3_bits >> 62) & 1u) |
        ((lead3_bits >> 63) & 1u) | ((lead4_bits >> 61) & 1u) |
        ((lead4_bits >> 62) & 1u) | ((lead4_bits >> 63) & 1u));
    const uint32_t pending1 = static_cast<uint32_t>(
        ((lead3_bits >> 63) & 1u) | ((lead4_bits >> 62) & 1u) |
        ((lead4_bits >> 63) & 1u));
    const uint32_t pending2 =
        static_cast<uint32_t>((lead4_bits >> 63) & 1u);
    pending = pending0 | (pending1 << 1) | (pending2 << 2);
    offset += 64;
  }

  return validate_utf8_scalar(bytes, length, offset, pending);
}
#endif

static bool validate_utf8(const char *input, size_t length) {
  const unsigned char *bytes = reinterpret_cast<const unsigned char *>(input);
#if UTF8_HAS_AVX512_TARGET
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
