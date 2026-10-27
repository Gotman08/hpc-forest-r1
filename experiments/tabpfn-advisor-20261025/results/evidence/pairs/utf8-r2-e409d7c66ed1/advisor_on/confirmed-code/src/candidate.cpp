#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#if defined(__SSE2__)
#include <emmintrin.h>
#endif
#include <cstdint>
#include <cstring>
#include <cmath>
#include <algorithm>
#include <omp.h>

static bool restricted_second_ok(unsigned int restriction, unsigned char byte) {
  switch (restriction) {
    case 1: return byte >= 0xA0;
    case 2: return byte <= 0x9F;
    case 3: return byte >= 0x90;
    case 4: return byte <= 0x8F;
    default: return true;
  }
}

static bool validate_scalar_tail(const unsigned char *bytes, size_t length,
                                 size_t index, unsigned int pending,
                                 unsigned int restriction) {
  while (index < length) {
    if (pending != 0) {
      const unsigned char byte = bytes[index++];
      if ((byte & 0xC0) != 0x80 || !restricted_second_ok(restriction, byte)) {
        return false;
      }
      --pending;
      restriction = 0;
      continue;
    }

    const unsigned char byte1 = bytes[index++];
    if (byte1 < 0x80) {
      continue;
    }
    if (byte1 < 0xE0) {
      if (byte1 < 0xC2 || index >= length || (bytes[index++] & 0xC0) != 0x80) {
        return false;
      }
      continue;
    }
    if (byte1 < 0xF0) {
      if (index + 1 >= length) {
        return false;
      }
      const unsigned char byte2 = bytes[index++];
      if ((byte2 & 0xC0) != 0x80 ||
          (byte1 == 0xE0 && byte2 < 0xA0) ||
          (byte1 == 0xED && byte2 >= 0xA0) ||
          (bytes[index++] & 0xC0) != 0x80) {
        return false;
      }
      continue;
    }

    if (byte1 > 0xF4 || index + 2 >= length) {
      return false;
    }
    const unsigned char byte2 = bytes[index++];
    if ((byte2 & 0xC0) != 0x80 ||
        (byte1 == 0xF0 && byte2 < 0x90) ||
        (byte1 == 0xF4 && byte2 > 0x8F) ||
        (bytes[index++] & 0xC0) != 0x80 ||
        (bytes[index++] & 0xC0) != 0x80) {
      return false;
    }
  }
  return pending == 0;
}

#if defined(__SSE2__)
static inline uint32_t byte_mask(__m128i value) {
  return static_cast<uint32_t>(_mm_movemask_epi8(value));
}

static inline unsigned int restriction_from_last_byte(unsigned char byte) {
  switch (byte) {
    case 0xE0: return 1;
    case 0xED: return 2;
    case 0xF0: return 3;
    case 0xF4: return 4;
    default: return 0;
  }
}
#endif

static bool validate_utf8(const char *input, size_t length) {
  const unsigned char *bytes = reinterpret_cast<const unsigned char *>(input);
#if defined(__SSE2__)
  size_t index = 0;
  uint32_t carry = 0;
  unsigned int restriction = 0;

  const __m128i bias = _mm_set1_epi8(static_cast<char>(0x80));
  const __m128i minus_one = _mm_set1_epi8(-1);
  const __m128i c0f = _mm_set1_epi8(0x0F);
  const __m128i c10 = _mm_set1_epi8(0x10);
  const __m128i c1f = _mm_set1_epi8(0x1F);
  const __m128i c20 = _mm_set1_epi8(0x20);
  const __m128i c40 = _mm_set1_epi8(0x40);
  const __m128i c41 = _mm_set1_epi8(0x41);
  const __m128i c5f = _mm_set1_epi8(0x5F);
  const __m128i c60 = _mm_set1_epi8(0x60);
  const __m128i c6f = _mm_set1_epi8(0x6F);
  const __m128i c70 = _mm_set1_epi8(0x70);
  const __m128i c75 = _mm_set1_epi8(0x75);
  const __m128i e0_value = _mm_set1_epi8(static_cast<char>(0xE0));
  const __m128i ed_value = _mm_set1_epi8(static_cast<char>(0xED));
  const __m128i f0_value = _mm_set1_epi8(static_cast<char>(0xF0));
  const __m128i f4_value = _mm_set1_epi8(static_cast<char>(0xF4));

  while (length - index >= 16) {
    const __m128i block = _mm_loadu_si128(
        reinterpret_cast<const __m128i *>(bytes + index));
    const uint32_t high_mask = byte_mask(block);

    if (high_mask == 0 && carry == 0 && restriction == 0) {
      index += 16;
      continue;
    }

    // Bias the vector once, so signed comparisons classify unsigned UTF-8 ranges.
    const __m128i transformed = _mm_xor_si128(block, bias);
    const __m128i continuation_bytes = _mm_and_si128(
        _mm_cmpgt_epi8(transformed, minus_one),
        _mm_cmpgt_epi8(c40, transformed));
    const __m128i lead2_bytes = _mm_and_si128(
        _mm_cmpgt_epi8(transformed, c41),
        _mm_cmpgt_epi8(c60, transformed));
    const __m128i lead3_bytes = _mm_and_si128(
        _mm_cmpgt_epi8(transformed, c5f),
        _mm_cmpgt_epi8(c70, transformed));
    const __m128i lead4_bytes = _mm_and_si128(
        _mm_cmpgt_epi8(transformed, c6f),
        _mm_cmpgt_epi8(c75, transformed));

    const uint32_t continuation_mask = byte_mask(continuation_bytes);
    const uint32_t lead2_mask = byte_mask(lead2_bytes);
    const uint32_t lead3_mask = byte_mask(lead3_bytes);
    const uint32_t lead4_mask = byte_mask(lead4_bytes);
    const uint32_t classified_mask = continuation_mask | lead2_mask |
                                     lead3_mask | lead4_mask;
    if ((high_mask & ~classified_mask) != 0) {
      return false;
    }

    const uint32_t expected_wide =
        ((lead2_mask | lead3_mask | lead4_mask) << 1) |
        ((lead3_mask | lead4_mask) << 2) |
        (lead4_mask << 3);
    const uint32_t expected_here = (expected_wide & 0xFFFFu) | carry;
    if (continuation_mask != expected_here) {
      return false;
    }

    // The shifted vector places each following byte in its lead's lane.
    const __m128i following = _mm_xor_si128(_mm_srli_si128(block, 1), bias);
    const uint32_t e0_mask = byte_mask(_mm_cmpeq_epi8(block, e0_value));
    const uint32_t ed_mask = byte_mask(_mm_cmpeq_epi8(block, ed_value));
    const uint32_t f0_mask = byte_mask(_mm_cmpeq_epi8(block, f0_value));
    const uint32_t f4_mask = byte_mask(_mm_cmpeq_epi8(block, f4_value));
    const uint32_t bad_e0_second = byte_mask(_mm_cmpgt_epi8(c20, following));
    const uint32_t bad_ed_second = byte_mask(_mm_cmpgt_epi8(following, c1f));
    const uint32_t bad_f0_second = byte_mask(_mm_cmpgt_epi8(c10, following));
    const uint32_t bad_f4_second = byte_mask(_mm_cmpgt_epi8(following, c0f));
    const uint32_t bad_restricted_pair =
        (e0_mask & bad_e0_second) |
        (ed_mask & bad_ed_second) |
        (f0_mask & bad_f0_second) |
        (f4_mask & bad_f4_second);
    if ((bad_restricted_pair & 0x7FFFU) != 0) {
      return false;
    }

    if (restriction != 0 && !restricted_second_ok(restriction, bytes[index])) {
      return false;
    }

    carry = expected_wide >> 16;
    restriction = restriction_from_last_byte(bytes[index + 15]);
    index += 16;
  }

  unsigned int pending = 0;
  for (uint32_t bits = carry; bits != 0; bits >>= 1) {
    ++pending;
  }
  return validate_scalar_tail(bytes, length, index, pending, restriction);
#else
  return validate_scalar_tail(bytes, length, 0, 0, 0);
#endif
}

extern "C" void run(const void *input1, const void *input2, void *output,
                    int n, int parameter, int threads) {
  *(uint32_t *)output = validate_utf8((const char *)input1, n);
}
