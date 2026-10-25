#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#if defined(__GNUC__) && !defined(__clang__) && \
    (defined(__x86_64__) || defined(__i386__))
#include <immintrin.h>
#define UTF8_CAN_COMPILE_AVX512BW 1
#else
#define UTF8_CAN_COMPILE_AVX512BW 0
#endif

static bool validate_utf8_scalar(const unsigned char *bytes, size_t length) {
  size_t index = 0;
  while (index < length) {
    const unsigned char byte1 = bytes[index++];
    if (byte1 < 0x80) {
      continue;
    }

    if (byte1 < 0xE0) {
      if (byte1 < 0xC2 || length - index < 1 ||
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

#if UTF8_CAN_COMPILE_AVX512BW
static bool validate_utf8_avx512(const unsigned char *bytes, size_t length)
    __attribute__((target("avx512f,avx512bw")));

static bool validate_utf8_avx512(const unsigned char *bytes, size_t length) {
  size_t index = 0;
  uint64_t carry = 0;
  unsigned int carry_special = 0;
  const uint64_t lane61 = UINT64_C(1) << 61;
  const uint64_t lane62 = UINT64_C(1) << 62;
  const uint64_t lane63 = UINT64_C(1) << 63;

  const __m512i c80 = _mm512_set1_epi8(static_cast<char>(0x80));
  const __m512i c90 = _mm512_set1_epi8(static_cast<char>(0x90));
  const __m512i c9f = _mm512_set1_epi8(static_cast<char>(0x9F));
  const __m512i ca0 = _mm512_set1_epi8(static_cast<char>(0xA0));
  const __m512i cc0 = _mm512_set1_epi8(static_cast<char>(0xC0));
  const __m512i cc2 = _mm512_set1_epi8(static_cast<char>(0xC2));
  const __m512i ce0 = _mm512_set1_epi8(static_cast<char>(0xE0));
  const __m512i ced = _mm512_set1_epi8(static_cast<char>(0xED));
  const __m512i cf0 = _mm512_set1_epi8(static_cast<char>(0xF0));
  const __m512i cf4 = _mm512_set1_epi8(static_cast<char>(0xF4));

  while (length - index >= 64) {
    const __m512i input =
        _mm512_loadu_si512(static_cast<const void *>(bytes + index));
    const uint64_t less80 = static_cast<uint64_t>(
        _mm512_cmp_epu8_mask(input, c80, _MM_CMPINT_LT));

    if (less80 == UINT64_MAX) {
      if (carry != 0 || carry_special != 0) {
        return false;
      }
      index += 64;
      continue;
    }

    const uint64_t lessC0 = static_cast<uint64_t>(
        _mm512_cmp_epu8_mask(input, cc0, _MM_CMPINT_LT));
    const uint64_t lessC2 = static_cast<uint64_t>(
        _mm512_cmp_epu8_mask(input, cc2, _MM_CMPINT_LT));
    const uint64_t lessE0 = static_cast<uint64_t>(
        _mm512_cmp_epu8_mask(input, ce0, _MM_CMPINT_LT));
    const uint64_t lessF0 = static_cast<uint64_t>(
        _mm512_cmp_epu8_mask(input, cf0, _MM_CMPINT_LT));
    const uint64_t atMostF4 = static_cast<uint64_t>(
        _mm512_cmp_epu8_mask(input, cf4, _MM_CMPINT_LE));

    const uint64_t ascii = less80;
    const uint64_t continuation = (~less80) & lessC0;
    const uint64_t lead2 = (~lessC2) & lessE0;
    const uint64_t lead3 = (~lessE0) & lessF0;
    const uint64_t lead4 = (~lessF0) & atMostF4;
    const uint64_t starts = lead2 | lead3 | lead4;
    const uint64_t threeOrFour = lead3 | lead4;
    const uint64_t allowed = ascii | continuation | starts;
    const uint64_t expected = (starts << 1) | (threeOrFour << 2) |
                              (lead4 << 3) | carry;
    if ((~allowed) != 0 || continuation != expected) {
      return false;
    }

    const uint64_t e0 = static_cast<uint64_t>(
        _mm512_cmpeq_epi8_mask(input, ce0));
    const uint64_t ed = static_cast<uint64_t>(
        _mm512_cmpeq_epi8_mask(input, ced));
    const uint64_t f0 = static_cast<uint64_t>(
        _mm512_cmpeq_epi8_mask(input, cf0));
    const uint64_t f4 = static_cast<uint64_t>(
        _mm512_cmpeq_epi8_mask(input, cf4));
    const uint64_t less90 = static_cast<uint64_t>(
        _mm512_cmp_epu8_mask(input, c90, _MM_CMPINT_LT));
    const uint64_t lessA0 = static_cast<uint64_t>(
        _mm512_cmp_epu8_mask(input, ca0, _MM_CMPINT_LT));
    const uint64_t greater8f = ~less90;
    const uint64_t greater9f = ~lessA0;

    if (((e0 << 1) & lessA0) != 0 ||
        ((ed << 1) & greater9f) != 0 ||
        ((f0 << 1) & less90) != 0 ||
        ((f4 << 1) & greater8f) != 0) {
      return false;
    }

    if ((carry_special == 1 && (lessA0 & 1) != 0) ||
        (carry_special == 2 && (greater9f & 1) != 0) ||
        (carry_special == 3 && (less90 & 1) != 0) ||
        (carry_special == 4 && (greater8f & 1) != 0)) {
      return false;
    }

    // The right shifts move each lead's off-block continuation bits to lane 0.
    carry = (starts >> 63) | (threeOrFour >> 62) | (lead4 >> 61);

    carry_special = 0;
    if ((e0 & lane63) != 0) {
      carry_special = 1;
    } else if ((ed & lane63) != 0) {
      carry_special = 2;
    } else if ((f0 & lane63) != 0) {
      carry_special = 3;
    } else if ((f4 & lane63) != 0) {
      carry_special = 4;
    }

    index += 64;
  }

  size_t pending = 0;
  uint64_t pendingBits = carry;
  while (pendingBits != 0) {
    if ((pendingBits & 1) == 0) {
      return false;
    }
    ++pending;
    pendingBits >>= 1;
  }

  const size_t tailLength = length - index;
  if (tailLength < pending || (carry_special != 0 && tailLength == 0)) {
    return false;
  }

  if (carry_special != 0) {
    const unsigned char first = bytes[index];
    if ((carry_special == 1 && first < 0xA0) ||
        (carry_special == 2 && first > 0x9F) ||
        (carry_special == 3 && first < 0x90) ||
        (carry_special == 4 && first > 0x8F)) {
      return false;
    }
  }
  for (size_t offset = 0; offset < pending; ++offset) {
    if ((bytes[index + offset] & 0xC0) != 0x80) {
      return false;
    }
  }

  index += pending;
  return validate_utf8_scalar(bytes + index, length - index);
}
#endif

static bool validate_utf8(const char *b, size_t length) {
  const unsigned char *bytes = reinterpret_cast<const unsigned char *>(b);
#if UTF8_CAN_COMPILE_AVX512BW
  if (length >= 64 && __builtin_cpu_supports("avx512f") &&
      __builtin_cpu_supports("avx512bw")) {
    return validate_utf8_avx512(bytes, length);
  }
#endif
  return validate_utf8_scalar(bytes, length);
}

extern "C" void run(const void *input1, const void *input2, void *output,
                    int n, int parameter, int threads) {
  const bool valid =
      n >= 0 && validate_utf8(static_cast<const char *>(input1),
                              static_cast<size_t>(n));
  *static_cast<uint32_t *>(output) = valid ? 1u : 0u;
}
