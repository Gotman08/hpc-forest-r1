#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#if defined(__SSE2__)
#include <emmintrin.h>
#endif

static bool validate_utf8_scalar(const unsigned char *bytes, size_t length) {
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

static bool validate_utf8(const char *b, size_t length) {
  const unsigned char *bytes = (const unsigned char *)b;
#if defined(__SSE2__)
  size_t index = 0;
  while (length - index >= 16) {
    const __m128i block = _mm_loadu_si128((const __m128i *)(bytes + index));
    unsigned int high_bits = (unsigned int)_mm_movemask_epi8(block);
    if (high_bits != 0) {
      size_t first_high_bit = 0;
      while ((high_bits & 1u) == 0u) {
        high_bits >>= 1;
        ++first_high_bit;
      }
      index += first_high_bit;
      break;
    }
    index += 16;
  }
  if (index == length) {
    return true;
  }
  return validate_utf8_scalar(bytes + index, length - index);
#else
  return validate_utf8_scalar(bytes, length);
#endif
}

extern "C" void run(const void *input1, const void *input2, void *output,
                    int n, int parameter, int threads) {
  *(uint32_t *)output = validate_utf8((const char *)input1, n);
}
