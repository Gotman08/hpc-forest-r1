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

  // The shifted load reads through offset + 64, so require 65 remaining bytes.
  // The final at-most-64 bytes are validated by the bounds-safe scalar path.
  while (length - offset >= 65) {
    const __m512i current = _mm512_loadu_si512(
        reinterpret_cast<const void *>(bytes + offset));
    const uint64_t ascii = static_cast<uint64_t>(_mm512_cmpeq_epi8_mask(
        _mm512_and_si512(current, _mm512_set1_epi8(static_cast<char>(0x80))),
        zero));

    // A complete ASCII block with no carried continuation needs no shifted load.
    if (pending == 0 && ascii == UINT64_MAX) {
      offset += 64;
      continue;
    }

    const uint64_t continuation = static_cast<uint64_t>(
        _mm512_cmpeq_epi8_mask(_mm512_and_si512(current, mask_c0), mask_80));
    const uint64_t lead2 = static_cast<uint64_t>(_mm512_cmpeq_epi8_mask(
                              _mm512_and_si512(current, mask_e0), mask_c0)) &
                          static_cast<uint64_t>(_mm512_cmpgt_epi8_mask(
                              _mm512_and_si512(current, mask_1f), one));
    const uint64_t lead3 = static_cast<uint64_t>(_mm512_cmpeq_epi8_mask(
        _mm512_and_si512(current, mask_f0), mask_e0));
    const uint64_t high4 = static_cast<uint64_t>(_mm512_cmpeq_epi8_mask(
        _mm512_and_si512(current, mask_f8), mask_f0));
    const uint64_t invalid4_low = static_cast<uint64_t>(_mm512_cmpgt_epi8_mask(
        _mm512_and_si512(current, mask_07), four));
    const uint64_t lead4 = high4 & ~invalid4_low;
    const uint64_t valid = ascii | continuation | lead2 | lead3 | lead4;

    if (valid != UINT64_MAX) {
      return false;
    }

    const __m512i next1 = _mm512_loadu_si512(
        reinterpret_cast<const void *>(bytes + offset + 1));
    const uint64_t e0 = static_cast<uint64_t>(_mm512_cmpeq_epi8_mask(
        current, _mm512_set1_epi8(static_cast<char>(0xE0))));
    const uint64_t ed = static_cast<uint64_t>(_mm512_cmpeq_epi8_mask(
        current, _mm512_set1_epi8(static_cast<char>(0xED))));
    const uint64_t f0 = static_cast<uint64_t>(_mm512_cmpeq_epi8_mask(
        current, _mm512_set1_epi8(static_cast<char>(0xF0))));
    const uint64_t f4 = static_cast<uint64_t>(_mm512_cmpeq_epi8_mask(
        current, mask_f4));

    const uint64_t bad_e0 = e0 & static_cast<uint64_t>(_mm512_cmpeq_epi8_mask(
        _mm512_and_si512(next1, mask_20), zero));
    const uint64_t bad_ed = ed & static_cast<uint64_t>(_mm512_cmpeq_epi8_mask(
        _mm512_and_si512(next1, mask_20), mask_20));
    const uint64_t bad_f0 = f0 & static_cast<uint64_t>(_mm512_cmpeq_epi8_mask(
        _mm512_and_si512(next1, mask_f0), mask_80));
    const uint64_t bad_f4 = f4 & ~static_cast<uint64_t>(_mm512_cmpeq_epi8_mask(
        _mm512_and_si512(next1, mask_30), zero));
    if ((bad_e0 | bad_ed | bad_f0 | bad_f4) != 0) {
      return false;
    }

    const unsigned __int128 expected_wide =
        (static_cast<unsigned __int128>(lead2) << 1) |
        (static_cast<unsigned __int128>(lead3) << 1) |
        (static_cast<unsigned __int128>(lead3) << 2) |
        (static_cast<unsigned __int128>(lead4) << 1) |
        (static_cast<unsigned __int128>(lead4) << 2) |
        (static_cast<unsigned __int128>(lead4) << 3);
    const uint64_t expected = static_cast<uint64_t>(expected_wide);
    if (continuation != (expected | pending)) {
      return false;
    }

    pending = static_cast<uint32_t>(expected_wide >> 64);
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
