#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
static bool validate_utf8_tail(const unsigned char *bytes, size_t length, size_t index) {
  while (index < length) {
    unsigned char byte1 = bytes[index++];
    if (byte1 < 0x80) {
      continue;
    }
    if (byte1 < 0xE0) {
      if (byte1 < 0xC2 || index == length || (bytes[index++] & 0xC0) != 0x80) {
        return false;
      }
    } else if (byte1 < 0xF0) {
      if (length - index < 2) {
        return false;
      }
      unsigned char byte2 = bytes[index++];
      if ((byte2 & 0xC0) != 0x80
          || (byte1 == 0xE0 && byte2 < 0xA0)
          || (byte1 == 0xED && byte2 >= 0xA0)
          || (bytes[index++] & 0xC0) != 0x80) {
        return false;
      }
    } else {
      if (length - index < 3) {
        return false;
      }
      unsigned char byte2 = bytes[index++];
      if ((byte2 & 0xC0) != 0x80
          || byte1 > 0xF4
          || (byte1 == 0xF0 && byte2 < 0x90)
          || (byte1 == 0xF4 && byte2 > 0x8F)
          || (bytes[index++] & 0xC0) != 0x80
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

  for (;;) {
    while (index < length && bytes[index] < 0x80) {
      ++index;
    }
    if (index == length) {
      return true;
    }
    if (length - index < 4) {
      return validate_utf8_tail(bytes, length, index);
    }

    const unsigned char lead = bytes[index];
    const unsigned char second = bytes[index + 1];
    const unsigned char third = bytes[index + 2];
    const unsigned char fourth = bytes[index + 3];
    const unsigned needs_two_more = static_cast<unsigned>(lead >= 0xE0);
    const unsigned needs_three_more = static_cast<unsigned>(lead >= 0xF0);

    const unsigned valid =
        static_cast<unsigned>(lead >= 0xC2)
        & static_cast<unsigned>(lead <= 0xF4)
        & static_cast<unsigned>((second & 0xC0) == 0x80)
        & ((!needs_two_more) | static_cast<unsigned>((third & 0xC0) == 0x80))
        & ((!needs_three_more) | static_cast<unsigned>((fourth & 0xC0) == 0x80))
        & static_cast<unsigned>((lead != 0xE0) | (second >= 0xA0))
        & static_cast<unsigned>((lead != 0xED) | (second < 0xA0))
        & static_cast<unsigned>((lead != 0xF0) | (second >= 0x90))
        & static_cast<unsigned>((lead != 0xF4) | (second <= 0x8F));

    if (valid == 0) {
      return false;
    }
    index += 2 + needs_two_more + needs_three_more;
  }
}

#include <cstdint>
#include <cstring>
#include <cmath>
#include <algorithm>
#include <omp.h>
extern "C" void run(const void* input1,const void* input2,void* output,int n,int parameter,int threads)
{*(uint32_t*)output=validate_utf8((const char*)input1,n);}
