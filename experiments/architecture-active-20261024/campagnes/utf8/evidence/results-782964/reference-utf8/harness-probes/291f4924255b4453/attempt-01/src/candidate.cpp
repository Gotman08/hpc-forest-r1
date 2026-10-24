#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <cstring>

#if defined(__SSE2__)
#include <emmintrin.h>
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
    if (byte1 < 0xE0) {
      if (index == length) {
        return false;
      }
      if (byte1 < 0xC2 || (bytes[index++] & 0xC0) != 0x80) {
        return false;
      }
    } else if (byte1 < 0xF0) {
      if (index + 1 >= length) {
        return false;
      }
      unsigned char byte2 = bytes[index++];
      if ((byte2 & 0xC0) != 0x80
          || (byte1 == 0xE0 && byte2 < 0xA0)
          || (byte1 == 0xED && 0xA0 <= byte2)
          || (bytes[index++] & 0xC0) != 0x80) {
        return false;
      }
    } else {
      if (index + 2 >= length) {
        return false;
      }
      int byte2 = bytes[index++];
      if ((byte2 & 0xC0) != 0x80
          || (byte1 > 0xF4 || (byte1 == 0xF0 && byte2 < 0x90) || (byte1 == 0xF4 && byte2 > 0x8F))
          || (bytes[index++] & 0xC0) != 0x80
          || (bytes[index++] & 0xC0) != 0x80) {
        return false;
      }
    }
  }
}

#if defined(__SSE2__)
static inline uint16_t utf8_vector_mask(__m128i value) {
  return (uint16_t)_mm_movemask_epi8(value);
}

static inline bool utf8_second_byte_ok(unsigned char byte, unsigned int check) {
  switch (check) {
    case 1: return byte >= 0xA0;
    case 2: return byte <= 0x9F;
    case 3: return byte >= 0x90;
    case 4: return byte <= 0x8F;
    default: return true;
  }
}

static bool validate_utf8_sse2(const char *b, size_t length) {
  const unsigned char *bytes = (const unsigned char *)b;
  const __m128i sign_bit = _mm_set1_epi8(-128);
  const __m128i prefix2_mask = _mm_set1_epi8(-32);
  const __m128i prefix2_value = _mm_set1_epi8(-64);
  const __m128i prefix3_mask = _mm_set1_epi8(-16);
  const __m128i prefix3_value = _mm_set1_epi8(-32);
  const __m128i prefix4_mask = _mm_set1_epi8(-8);
  const __m128i prefix4_value = _mm_set1_epi8(-16);
  const __m128i continuation_mask = _mm_set1_epi8(-64);
  const __m128i continuation_value = _mm_set1_epi8(-128);
  const __m128i invalid_short_mask = _mm_set1_epi8(-2);
  const __m128i invalid_short_value = _mm_set1_epi8(-64);
  const __m128i threshold_f4 = _mm_set1_epi8(0x74);

  size_t index = 0;
  size_t safe_index = 0;
  uint32_t carry = 0;
  unsigned int pending_check = 0;

  while (length - index >= 16) {
    if (pending_check != 0) {
      if (!utf8_second_byte_ok(bytes[index], pending_check)) {
        return false;
      }
      pending_check = 0;
    }

    __m128i value;
    std::memcpy(&value, bytes + index, sizeof(value));
    const uint16_t high_mask = utf8_vector_mask(value);

    if (high_mask == 0) {
      if (carry != 0) {
        return false;
      }
      index += 16;
      safe_index = index;
      continue;
    }

    const uint16_t ascii = (uint16_t)~high_mask;
    const uint16_t continuation = utf8_vector_mask(_mm_cmpeq_epi8(
        _mm_and_si128(value, continuation_mask), continuation_value));
    const uint16_t lead2_candidates = utf8_vector_mask(_mm_cmpeq_epi8(
        _mm_and_si128(value, prefix2_mask), prefix2_value));
    const uint16_t lead3 = utf8_vector_mask(_mm_cmpeq_epi8(
        _mm_and_si128(value, prefix3_mask), prefix3_value));
    const uint16_t lead4_candidates = utf8_vector_mask(_mm_cmpeq_epi8(
        _mm_and_si128(value, prefix4_mask), prefix4_value));
    const uint16_t invalid_short = utf8_vector_mask(_mm_cmpeq_epi8(
        _mm_and_si128(value, invalid_short_mask), invalid_short_value));
    if (invalid_short != 0) {
      return false;
    }

    const __m128i unsigned_order = _mm_xor_si128(value, sign_bit);
    const uint16_t above_f4 = utf8_vector_mask(
        _mm_cmpgt_epi8(unsigned_order, threshold_f4));
    const uint16_t lead2 = lead2_candidates;
    const uint16_t lead4 = (uint16_t)(lead4_candidates & (uint16_t)~above_f4);

    if ((uint16_t)(ascii | continuation | lead2 | lead3 | lead4) != UINT16_MAX) {
      return false;
    }

    const uint32_t lead24 = (uint32_t)(lead2 | lead3 | lead4);
    const uint32_t lead34 = (uint32_t)(lead3 | lead4);
    const uint32_t local_expected = (lead24 << 1) | (lead34 << 2) | ((uint32_t)lead4 << 3);
    const uint32_t expected = local_expected | carry;
    if ((uint16_t)expected != continuation) {
      return false;
    }

    // Restricted second-byte checks are rare; inspect only lanes with such starters.
    const uint16_t e0 = utf8_vector_mask(_mm_cmpeq_epi8(value, _mm_set1_epi8(-32)));
    const uint16_t ed = utf8_vector_mask(_mm_cmpeq_epi8(value, _mm_set1_epi8(-19)));
    const uint16_t f0 = utf8_vector_mask(_mm_cmpeq_epi8(value, _mm_set1_epi8(-16)));
    const uint16_t f4 = utf8_vector_mask(_mm_cmpeq_epi8(value, _mm_set1_epi8(-12)));
    const uint16_t restricted_leads = (uint16_t)(e0 | ed | f0 | f4);
    pending_check = 0;
    if (restricted_leads != 0) {
      for (unsigned int lane = 0; lane < 16; ++lane) {
        if ((restricted_leads & (uint16_t)(1u << lane)) == 0) {
          continue;
        }
        const unsigned char lead = bytes[index + lane];
        const unsigned int check = lead == 0xE0 ? 1u
            : lead == 0xED ? 2u
            : lead == 0xF0 ? 3u : 4u;
        if (lane == 15) {
          pending_check = check;
        } else if (!utf8_second_byte_ok(bytes[index + lane + 1], check)) {
          return false;
        }
      }
    }

    carry = local_expected >> 16;
    index += 16;
    if (carry == 0 && pending_check == 0) {
      safe_index = index;
    }
  }

  const size_t scalar_start = (carry == 0 && pending_check == 0) ? index : safe_index;
  return validate_utf8_scalar((const char *)(bytes + scalar_start), length - scalar_start);
}
#endif

static bool validate_utf8(const char *b, size_t length) {
#if defined(__SSE2__)
  return validate_utf8_sse2(b, length);
#else
  return validate_utf8_scalar(b, length);
#endif
}

#include <cstdint>
#include <cstring>
#include <cmath>
#include <algorithm>
#include <omp.h>
extern "C" void run(const void* input1,const void* input2,void* output,int n,int parameter,int threads)
{*(uint32_t*)output=validate_utf8((const char*)input1,n);}
