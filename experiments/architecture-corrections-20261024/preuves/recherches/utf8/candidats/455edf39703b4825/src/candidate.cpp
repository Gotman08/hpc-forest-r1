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
__attribute__((target("avx512f,avx512bw")))
static bool validate_utf8_avx512bw(const unsigned char *bytes, size_t length) {
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
  const __m512i mask_f8 = _mm512_set1_epi8(static_cast<char>(0xF8));

  // The shifted masked load can address byte offset + 64, so 65 remaining
  // bytes are required. The final at-most-64 bytes use the scalar validator.
  while (length - offset >= 65) {
    const __m512i current = _mm512_loadu_si512(bytes + offset);

    const uint64_t ascii = static_cast<uint64_t>(_mm512_cmpeq_epi8_mask(
        _mm512_and_si512(current, _mm512_set1_epi8(static_cast<char>(0x80))),
        zero));
    const uint64_t continuation = static_cast<uint64_t>(
        _mm512_cmpeq_epi8_mask(_mm512_and_si512(current, mask_c0), mask_80));
    const uint64_t lead2 =
        static_cast<uint64_t>(_mm512_cmpeq_epi8_mask(
            _mm512_and_si512(current, mask_e0), mask_c0)) &
        static_cast<uint64_t>(_mm512_cmpgt_epi8_mask(
            _mm512_and_si512(current, mask_1f), one));
    const uint64_t lead3 = static_cast<uint64_t>(_mm512_cmpeq_epi8_mask(
        _mm512_and_si512(current, mask_f0), mask_e0));
    const uint64_t high4 = static_cast<uint64_t>(_mm512_cmpeq_epi8_mask(
        _mm512_and_si512(current, mask_f8), mask_f0));
    const uint64_t invalid4_low = static_cast<uint64_t>(
        _mm512_cmpgt_epi8_mask(_mm512_and_si512(current, mask_07), four));
    const uint64_t lead4 = high4 & ~invalid4_low;
    if ((ascii | continuation | lead2 | lead3 | lead4) != UINT64_MAX) {
      return false;
    }

    const uint64_t e0 = static_cast<uint64_t>(_mm512_cmpeq_epi8_mask(
        current, _mm512_set1_epi8(static_cast<char>(0xE0))));
    const uint64_t ed = static_cast<uint64_t>(_mm512_cmpeq_epi8_mask(
        current, _mm512_set1_epi8(static_cast<char>(0xED))));
    const uint64_t f0 = static_cast<uint64_t>(_mm512_cmpeq_epi8_mask(
        current, _mm512_set1_epi8(static_cast<char>(0xF0))));
    const uint64_t f4 = static_cast<uint64_t>(_mm512_cmpeq_epi8_mask(
        current, _mm512_set1_epi8(static_cast<char>(0xF4))));
    const uint64_t special = e0 | ed | f0 | f4;

    // Only lanes containing E0, ED, F0, or F4 need their second byte loaded.
    // Since the loop requires 65 bytes, even an active lane 63 is in bounds.
    const __m512i next1 = _mm512_maskz_loadu_epi8(
        static_cast<__mmask64>(special), bytes + offset + 1);
    const uint64_t second_bit5 = static_cast<uint64_t>(
        _mm512_cmpeq_epi8_mask(_mm512_and_si512(next1, mask_20), zero));
    const uint64_t bad_e0 = e0 & second_bit5;
    const uint64_t bad_ed = ed & ~static_cast<uint64_t>(
        _mm512_cmpeq_epi8_mask(_mm512_and_si512(next1, mask_20), zero));
    const uint64_t bad_f0 = f0 & static_cast<uint64_t>(_mm512_cmpeq_epi8_mask(
        _mm512_and_si512(next1, mask_f0), mask_80));
    const uint64_t bad_f4 = f4 & ~static_cast<uint64_t>(
        _mm512_cmpeq_epi8_mask(_mm512_and_si512(next1, mask_30), zero));
    if ((bad_e0 | bad_ed | bad_f0 | bad_f4) != 0) {
      return false;
    }

    const uint64_t expected = (lead2 << 1) | (lead3 << 1) | (lead3 << 2) |
                              (lead4 << 1) | (lead4 << 2) | (lead4 << 3);
    if (continuation != (expected | pending)) {
      return false;
    }

    // Carry the continuation positions that extend beyond this 64-byte block.
    uint64_t next_pending = lead2 >> 63;
    if ((lead3 >> 62) != 0) {
      next_pending |= 1;
    }
    next_pending |= (lead3 >> 63) << 1;
    if ((lead4 >> 61) != 0) {
      next_pending |= 1;
    }
    if ((lead4 >> 62) != 0) {
      next_pending |= 2;
    }
    next_pending |= (lead4 >> 63) << 2;
    pending = static_cast<uint32_t>(next_pending);
    offset += 64;
  }

  return validate_utf8_scalar(bytes, length, offset, pending);
}
#endif

static bool validate_utf8(const char *input, size_t length) {
  const unsigned char *bytes = reinterpret_cast<const unsigned char *>(input);
#if UTF8_HAS_AVX512BW_TARGET
  if (length >= 65) {
    return validate_utf8_avx512bw(bytes, length);
  }
#endif
  return validate_utf8_scalar(bytes, length, 0, 0);
}

extern "C" void run(const void *input1, const void *input2, void *output,
                    int n, int parameter, int threads) {
  *(uint32_t *)output = validate_utf8((const char *)input1, n);
}
