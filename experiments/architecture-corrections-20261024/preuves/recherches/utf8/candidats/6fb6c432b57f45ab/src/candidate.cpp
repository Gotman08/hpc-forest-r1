#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <immintrin.h>
#include <cstdint>
#include <cstring>
#include <cmath>
#include <algorithm>
#include <omp.h>

enum {
  kRestrictionNone = 0,
  kRestrictionE0 = 1,
  kRestrictionED = 2,
  kRestrictionF0 = 3,
  kRestrictionF4 = 4
};

static bool restricted_second_byte_valid(unsigned char byte, unsigned int restriction) {
  switch (restriction) {
  case kRestrictionE0:
    return byte >= 0xA0;
  case kRestrictionED:
    return byte < 0xA0;
  case kRestrictionF0:
    return byte >= 0x90;
  case kRestrictionF4:
    return byte < 0x90;
  default:
    return true;
  }
}

static bool validate_utf8_scalar_tail(const unsigned char *bytes, size_t length,
                                      size_t index, uint32_t pending,
                                      unsigned int restriction) {
  unsigned int pending_count = ((pending & 1u) != 0u) +
                               ((pending & 2u) != 0u) +
                               ((pending & 4u) != 0u);
  bool check_restricted_second = restriction != kRestrictionNone;

  while (index < length) {
    const unsigned char byte1 = bytes[index++];

    if (pending_count != 0) {
      if ((byte1 & 0xC0) != 0x80) {
        return false;
      }
      if (check_restricted_second &&
          !restricted_second_byte_valid(byte1, restriction)) {
        return false;
      }
      check_restricted_second = false;
      --pending_count;
      continue;
    }

    if (byte1 <= 0x7F) {
      continue;
    }

    if (byte1 >= 0xC2 && byte1 <= 0xDF) {
      if (length - index < 1) {
        return false;
      }
      if ((bytes[index++] & 0xC0) != 0x80) {
        return false;
      }
    } else if (byte1 >= 0xE0 && byte1 <= 0xEF) {
      if (length - index < 2) {
        return false;
      }
      const unsigned char byte2 = bytes[index++];
      const unsigned char byte3 = bytes[index++];
      if ((byte2 & 0xC0) != 0x80 ||
          (byte1 == 0xE0 && byte2 < 0xA0) ||
          (byte1 == 0xED && byte2 >= 0xA0) ||
          (byte3 & 0xC0) != 0x80) {
        return false;
      }
    } else if (byte1 >= 0xF0 && byte1 <= 0xF4) {
      if (length - index < 3) {
        return false;
      }
      const unsigned char byte2 = bytes[index++];
      const unsigned char byte3 = bytes[index++];
      const unsigned char byte4 = bytes[index++];
      if ((byte2 & 0xC0) != 0x80 ||
          (byte1 == 0xF0 && byte2 < 0x90) ||
          (byte1 == 0xF4 && byte2 >= 0x90) ||
          (byte3 & 0xC0) != 0x80 ||
          (byte4 & 0xC0) != 0x80) {
        return false;
      }
    } else {
      return false;
    }
  }

  return pending_count == 0;
}

static inline __attribute__((target("avx2"), always_inline)) bool
validate_avx2_block(const unsigned char *bytes, uint32_t *pending,
                    unsigned int *restriction) {
  const __m256i value = _mm256_loadu_si256(
      reinterpret_cast<const __m256i *>(bytes));

  // Signed constants represent their corresponding byte values for cmpgt.
  const __m256i c0 = _mm256_set1_epi8(-64);
  const __m256i byte80 = _mm256_set1_epi8(-128);
  const __m256i c1 = _mm256_set1_epi8(-63);
  const __m256i e0 = _mm256_set1_epi8(-32);
  const __m256i df = _mm256_set1_epi8(-33);
  const __m256i f0 = _mm256_set1_epi8(-16);
  const __m256i ef = _mm256_set1_epi8(-17);
  const __m256i f5 = _mm256_set1_epi8(-11);
  const __m256i a0 = _mm256_set1_epi8(-96);
  const __m256i byte90 = _mm256_set1_epi8(-112);

  const __m256i continuation = _mm256_cmpeq_epi8(
      _mm256_and_si256(value, c0), byte80);
  const __m256i lead2 = _mm256_and_si256(
      _mm256_cmpgt_epi8(value, c1), _mm256_cmpgt_epi8(e0, value));
  const __m256i lead3 = _mm256_and_si256(
      _mm256_cmpgt_epi8(value, df), _mm256_cmpgt_epi8(f0, value));
  const __m256i lead4 = _mm256_and_si256(
      _mm256_cmpgt_epi8(value, ef), _mm256_cmpgt_epi8(f5, value));

  const uint32_t non_ascii_mask = static_cast<uint32_t>(
      _mm256_movemask_epi8(value));
  const uint32_t continuation_mask = static_cast<uint32_t>(
      _mm256_movemask_epi8(continuation));
  const uint32_t lead2_mask = static_cast<uint32_t>(
      _mm256_movemask_epi8(lead2));
  const uint32_t lead3_mask = static_cast<uint32_t>(
      _mm256_movemask_epi8(lead3));
  const uint32_t lead4_mask = static_cast<uint32_t>(
      _mm256_movemask_epi8(lead4));
  const uint32_t ascii_mask = ~non_ascii_mask;
  const uint32_t class_mask = ascii_mask | continuation_mask | lead2_mask |
                              lead3_mask | lead4_mask;
  if (class_mask != 0xFFFFFFFFu) {
    return false;
  }

  if (*restriction != kRestrictionNone &&
      !restricted_second_byte_valid(bytes[0], *restriction)) {
    return false;
  }

  const uint32_t e0_mask = static_cast<uint32_t>(_mm256_movemask_epi8(
      _mm256_cmpeq_epi8(value, e0)));
  const uint32_t ed_mask = static_cast<uint32_t>(_mm256_movemask_epi8(
      _mm256_cmpeq_epi8(value, _mm256_set1_epi8(-19))));
  const uint32_t f0_mask = static_cast<uint32_t>(_mm256_movemask_epi8(
      _mm256_cmpeq_epi8(value, f0)));
  const uint32_t f4_mask = static_cast<uint32_t>(_mm256_movemask_epi8(
      _mm256_cmpeq_epi8(value, _mm256_set1_epi8(-12))));
  const uint32_t below_a0 = static_cast<uint32_t>(_mm256_movemask_epi8(
      _mm256_cmpgt_epi8(a0, value)));
  const uint32_t below_90 = static_cast<uint32_t>(_mm256_movemask_epi8(
      _mm256_cmpgt_epi8(byte90, value)));
  const uint32_t invalid_restricted_second =
      ((e0_mask << 1) & below_a0) |
      ((ed_mask << 1) & ~below_a0) |
      ((f0_mask << 1) & below_90) |
      ((f4_mask << 1) & ~below_90);
  if (invalid_restricted_second != 0) {
    return false;
  }

  const uint64_t expected_continuations =
      (static_cast<uint64_t>(lead2_mask | lead3_mask | lead4_mask) << 1) |
      (static_cast<uint64_t>(lead3_mask | lead4_mask) << 2) |
      (static_cast<uint64_t>(lead4_mask) << 3);
  const uint32_t expected_here =
      static_cast<uint32_t>(expected_continuations) | *pending;
  if (continuation_mask != expected_here) {
    return false;
  }

  *pending = static_cast<uint32_t>(expected_continuations >> 32);
  if ((e0_mask & 0x80000000u) != 0) {
    *restriction = kRestrictionE0;
  } else if ((ed_mask & 0x80000000u) != 0) {
    *restriction = kRestrictionED;
  } else if ((f0_mask & 0x80000000u) != 0) {
    *restriction = kRestrictionF0;
  } else if ((f4_mask & 0x80000000u) != 0) {
    *restriction = kRestrictionF4;
  } else {
    *restriction = kRestrictionNone;
  }
  return true;
}

__attribute__((target("avx2")))
static bool validate_utf8_avx2(const unsigned char *bytes, size_t length) {
  size_t offset = 0;
  uint32_t pending = 0;
  unsigned int restriction = kRestrictionNone;

  while (length - offset >= 64) {
    if (!validate_avx2_block(bytes + offset, &pending, &restriction) ||
        !validate_avx2_block(bytes + offset + 32, &pending, &restriction)) {
      return false;
    }
    offset += 64;
  }

  while (length - offset >= 32) {
    if (!validate_avx2_block(bytes + offset, &pending, &restriction)) {
      return false;
    }
    offset += 32;
  }

  return validate_utf8_scalar_tail(bytes, length, offset, pending, restriction);
}

static bool validate_utf8(const char *b, size_t length) {
  return validate_utf8_avx2(reinterpret_cast<const unsigned char *>(b), length);
}

extern "C" void run(const void *input1, const void *input2, void *output,
                    int n, int parameter, int threads) {
  *(uint32_t *)output = validate_utf8((const char *)input1, n);
}
