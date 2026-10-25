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

  const __m512i c80 = _mm512_set1_epi8(static_cast<char>(0x80));
  const __m512i cBF = _mm512_set1_epi8(static_cast<char>(0xBF));
  const __m512i cC0 = _mm512_set1_epi8(static_cast<char>(0xC0));
  const __m512i cC2 = _mm512_set1_epi8(static_cast<char>(0xC2));
  const __m512i cE0 = _mm512_set1_epi8(static_cast<char>(0xE0));
  const __m512i cED = _mm512_set1_epi8(static_cast<char>(0xED));
  const __m512i cEF = _mm512_set1_epi8(static_cast<char>(0xEF));
  const __m512i cF0 = _mm512_set1_epi8(static_cast<char>(0xF0));
  const __m512i cF4 = _mm512_set1_epi8(static_cast<char>(0xF4));
  const __m512i zero = _mm512_setzero_si512();
  const __m512i mask20 = _mm512_set1_epi8(0x20);
  const __m512i mask30 = _mm512_set1_epi8(0x30);
  const __m512i maskF0 = _mm512_set1_epi8(static_cast<char>(0xF0));

  // The shifted load reaches offset + 64; leave the final at most 64 bytes
  // to the scalar validator so no vector load can pass the input boundary.
  while (length - offset >= 65) {
    const __m512i current = _mm512_loadu_si512(bytes + offset);

    const __mmask64 ascii =
        _mm512_cmp_epu8_mask(current, c80, _MM_CMPINT_LT);
    const __mmask64 continuation =
        _mm512_cmp_epu8_mask(current, c80, _MM_CMPINT_NLT) &
        _mm512_cmp_epu8_mask(current, cC0, _MM_CMPINT_LT);
    const __mmask64 lead2 =
        _mm512_cmp_epu8_mask(current, cC2, _MM_CMPINT_NLT) &
        _mm512_cmp_epu8_mask(current, cE0, _MM_CMPINT_LT);
    const __mmask64 lead3 =
        _mm512_cmp_epu8_mask(current, cE0, _MM_CMPINT_NLT) &
        _mm512_cmp_epu8_mask(current, cF0, _MM_CMPINT_LT);
    const __mmask64 lead4 =
        _mm512_cmp_epu8_mask(current, cF0, _MM_CMPINT_NLT) &
        _mm512_cmp_epu8_mask(current, cF4, _MM_CMPINT_LE);
    const __mmask64 valid = ascii | continuation | lead2 | lead3 | lead4;
    if (valid != UINT64_MAX) {
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

    // Carry expected continuation bits beyond lane 63 into the next block.
    const uint32_t carry1 = static_cast<uint32_t>(
        ((lead2_bits >> 63) & 1u) | ((lead3_bits >> 63) & 1u) |
        ((lead3_bits >> 62) & 1u) | ((lead4_bits >> 63) & 1u) |
        ((lead4_bits >> 62) & 1u) | ((lead4_bits >> 61) & 1u));
    const uint32_t carry2 = static_cast<uint32_t>(
        ((lead3_bits >> 63) & 1u) | ((lead4_bits >> 63) & 1u) |
        ((lead4_bits >> 62) & 1u));
    const uint32_t carry3 = static_cast<uint32_t>((lead4_bits >> 63) & 1u);
    pending = carry1 | (carry2 << 1) | (carry3 << 2);

    const __mmask64 e0 = _mm512_cmpeq_epi8_mask(
        current, _mm512_set1_epi8(static_cast<char>(0xE0)));
    const __mmask64 ed = _mm512_cmpeq_epi8_mask(current, cED);
    const __mmask64 f0 = _mm512_cmpeq_epi8_mask(current, cF0);
    const __mmask64 f4 = _mm512_cmpeq_epi8_mask(current, cF4);
    const __mmask64 restricted_leads = e0 | ed | f0 | f4;

    // Only these lead classes need second-byte range restrictions. If present,
    // the loop bound guarantees this 64-byte shifted load stays in-bounds.
    if (restricted_leads != 0) {
      const __m512i next1 = _mm512_loadu_si512(bytes + offset + 1);
      const __mmask64 bad_e0 = e0 & _mm512_cmpeq_epi8_mask(
                                    _mm512_and_si512(next1, mask20), zero);
      const __mmask64 bad_ed = ed & _mm512_cmpeq_epi8_mask(
                                    _mm512_and_si512(next1, mask20), mask20);
      const __mmask64 bad_f0 = f0 & _mm512_cmpeq_epi8_mask(
                                    _mm512_and_si512(next1, maskF0), c80);
      const __mmask64 bad_f4 = f4 & ~_mm512_cmpeq_epi8_mask(
                                      _mm512_and_si512(next1, mask30), zero);
      if ((bad_e0 | bad_ed | bad_f0 | bad_f4) != 0) {
        return false;
      }
    }

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
