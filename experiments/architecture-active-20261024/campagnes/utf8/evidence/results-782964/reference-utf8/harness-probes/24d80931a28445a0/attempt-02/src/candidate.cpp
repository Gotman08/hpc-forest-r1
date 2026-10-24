#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#if defined(__SSE2__)
#include <emmintrin.h>
#endif

static bool decode_utf8_one(const unsigned char *bytes, size_t length,
                            size_t *index) {
  size_t i = *index;
  if (i >= length) {
    return false;
  }

  unsigned char byte1 = bytes[i++];
  if (byte1 < 0x80) {
    *index = i;
    return true;
  }

  if (byte1 < 0xE0) {
    if (i >= length) {
      return false;
    }
    unsigned char byte2 = bytes[i];
    if (byte1 < 0xC2 || (byte2 & 0xC0) != 0x80) {
      return false;
    }
    *index = i + 1;
    return true;
  }

  if (byte1 < 0xF0) {
    if (length - i < 2) {
      return false;
    }
    unsigned char byte2 = bytes[i];
    unsigned char byte3 = bytes[i + 1];
    if ((byte2 & 0xC0) != 0x80
        || (byte1 == 0xE0 && byte2 < 0xA0)
        || (byte1 == 0xED && byte2 >= 0xA0)
        || (byte3 & 0xC0) != 0x80) {
      return false;
    }
    *index = i + 2;
    return true;
  }

  if (length - i < 3) {
    return false;
  }
  unsigned char byte2 = bytes[i];
  unsigned char byte3 = bytes[i + 1];
  unsigned char byte4 = bytes[i + 2];
  if ((byte2 & 0xC0) != 0x80
      || byte1 > 0xF4
      || (byte1 == 0xF0 && byte2 < 0x90)
      || (byte1 == 0xF4 && byte2 > 0x8F)
      || (byte3 & 0xC0) != 0x80
      || (byte4 & 0xC0) != 0x80) {
    return false;
  }
  *index = i + 3;
  return true;
}

static bool validate_utf8_scalar(const unsigned char *bytes, size_t length) {
  size_t index = 0;
  while (index < length) {
    if (!decode_utf8_one(bytes, length, &index)) {
      return false;
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
    if ((unsigned int)_mm_movemask_epi8(block) == 0U) {
      index += 16;
      continue;
    }

    // The scalar window starts at a known code-point boundary. Decode through
    // at least 64 bytes before resuming SIMD, keeping the next index on a
    // code-point boundary even if a character crosses the window end.
    const size_t window_start = index;
    const size_t window_end =
        (length - window_start > 64) ? window_start + 64 : length;
    do {
      if (!decode_utf8_one(bytes, length, &index)) {
        return false;
      }
    } while (index < window_end);
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
