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
  const __m128i zero = _mm_setzero_si128();
  const __m128i sign_bit = _mm_set1_epi8(-128);
  const __m128i threshold_0f = _mm_set1_epi8(0x0F);
  const __m128i threshold_10 = _mm_set1_epi8(0x10);
  const __m128i threshold_1f = _mm_set1_epi8(0x1F);
  const __m128i threshold_20 = _mm_set1_epi8(0x20);
  const __m128i threshold_40 = _mm_set1_epi8(0x40);
  const __m128i threshold_41 = _mm_set1_epi8(0x41);
  const __m128i threshold_5f = _mm_set1_epi8(0x5F);
  const __m128i threshold_60 = _mm_set1_epi8(0x60);
  const __m128i threshold_6f = _mm_set1_epi8(0x6F);
  const __m128i threshold_70 = _mm_set1_epi8(0x70);
  const __m128i threshold_75 = _mm_set1_epi8(0x75);

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
    const __m128i high_lanes = _mm_cmpgt_epi8(zero, value);
    const uint16_t high_mask = utf8_vector_mask(high_lanes);

    if (high_mask == 0) {
      if (carry != 0) {
        return false;
      }
      index += 16;
      safe_index = index;
      continue;
    }

    const __m128i unsigned_order = _mm_xor_si128(value, sign_bit);
    const uint16_t ascii = (uint16_t)~high_mask;
    const uint16_t continuation = utf8_vector_mask(
        _mm_and_si128(high_lanes,
            _mm_cmpgt_epi8(threshold_40, unsigned_order)));
    const uint16_t lead2 = utf8_vector_mask(_mm_and_si128(
        _mm_cmpgt_epi8(unsigned_order, threshold_41),
        _mm_cmpgt_epi8(threshold_60, unsigned_order)));
    const uint16_t lead3 = utf8_vector_mask(_mm_and_si128(
        _mm_cmpgt_epi8(unsigned_order, threshold_5f),
        _mm_cmpgt_epi8(threshold_70, unsigned_order)));
    const uint16_t lead4 = utf8_vector_mask(_mm_and_si128(
        _mm_cmpgt_epi8(unsigned_order, threshold_6f),
        _mm_cmpgt_epi8(threshold_75, unsigned_order)));

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

    const uint16_t e0 = utf8_vector_mask(_mm_cmpeq_epi8(value, _mm_set1_epi8(-32)));
    const uint16_t ed = utf8_vector_mask(_mm_cmpeq_epi8(value, _mm_set1_epi8(-19)));
    const uint16_t f0 = utf8_vector_mask(_mm_cmpeq_epi8(value, _mm_set1_epi8(-16)));
    const uint16_t f4 = utf8_vector_mask(_mm_cmpeq_epi8(value, _mm_set1_epi8(-12)));
    const __m128i next_value = _mm_srli_si128(value, 1);
    const __m128i next_order = _mm_xor_si128(next_value, sign_bit);
    const uint16_t below_a0 = utf8_vector_mask(_mm_cmpgt_epi8(threshold_20, next_order));
    const uint16_t above_9f = utf8_vector_mask(_mm_cmpgt_epi8(next_order, threshold_1f));
    const uint16_t below_90 = utf8_vector_mask(_mm_cmpgt_epi8(threshold_10, next_order));
    const uint16_t above_8f = utf8_vector_mask(_mm_cmpgt_epi8(next_order, threshold_0f));
    const uint32_t bad_second =
        (((uint32_t)e0 << 1) & below_a0)
        | (((uint32_t)ed << 1) & above_9f)
        | (((uint32_t)f0 << 1) & below_90)
        | (((uint32_t)f4 << 1) & above_8f);
    if (bad_second != 0) {
      return false;
    }

    pending_check = 0;
    if (e0 & 0x8000u) {
      pending_check = 1;
    } else if (ed & 0x8000u) {
      pending_check = 2;
    } else if (f0 & 0x8000u) {
      pending_check = 3;
    } else if (f4 & 0x8000u) {
      pending_check = 4;
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
