#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#if defined(__SSE2__)
#include <emmintrin.h>
#endif

static bool validate_utf8_scalar(const unsigned char *bytes, size_t length) {
  size_t index = 0;
  while (index < length) {
    unsigned char byte1 = bytes[index++];
    if (byte1 < 0x80) {
      continue;
    }
    if (byte1 < 0xE0) {
      // Two-byte form.
      if (index == length) {
        return false;
      }
      if (byte1 < 0xC2 || (bytes[index++] & 0xC0) != 0x80) {
        return false;
      }
    } else if (byte1 < 0xF0) {
      // Three-byte form.
      if (length - index < 2) {
        return false;
      }
      unsigned char byte2 = bytes[index++];
      if ((byte2 & 0xC0) != 0x80
          // Overlong? 5 most significant bits must not all be zero.
          || (byte1 == 0xE0 && byte2 < 0xA0)
          // Check for illegal surrogate codepoints.
          || (byte1 == 0xED && 0xA0 <= byte2)
          // Third byte trailing-byte test.
          || (bytes[index++] & 0xC0) != 0x80) {
        return false;
      }
    } else {
      // Four-byte form.
      if (length - index < 3) {
        return false;
      }
      int byte2 = bytes[index++];
      if ((byte2 & 0xC0) != 0x80
          // Check that 1 <= plane <= 16.
          || (byte1 > 0xF4 || (byte1 == 0xF0 && byte2 < 0x90) || (byte1 == 0xF4 && byte2 > 0x8F))
          // Third byte trailing-byte test
          || (bytes[index++] & 0xC0) != 0x80
          // Fourth byte trailing-byte test
          || (bytes[index++] & 0xC0) != 0x80) {
        return false;
      }
    }
  }
  return true;
}

static bool validate_utf8(const char *b, size_t length) {
  const unsigned char *bytes = (const unsigned char *)b;
  size_t index = 0;
#if defined(__SSE2__)
  while (length - index >= 16) {
    const __m128i block =
        _mm_loadu_si128((const __m128i *)(bytes + index));
    unsigned int high_bits = (unsigned int)_mm_movemask_epi8(block);
    if (high_bits != 0U) {
      // Start at this block's boundary; the scalar decoder validates the
      // entire suffix, including any ASCII prefix and the first high-bit byte.
      return validate_utf8_scalar(bytes + index, length - index);
    }
    index += 16;
  }
#endif
  return validate_utf8_scalar(bytes + index, length - index);
}

#include <cstdint>
#include <cstring>
#include <cmath>
#include <algorithm>
#include <omp.h>
extern "C" void run(const void* input1,const void* input2,void* output,int n,int parameter,int threads)
{*(uint32_t*)output=validate_utf8((const char*)input1,n);}
