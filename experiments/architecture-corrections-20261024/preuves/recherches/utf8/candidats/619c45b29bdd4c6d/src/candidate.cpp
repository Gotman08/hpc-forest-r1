#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <algorithm>
#include <cmath>
#include <cstdint>
#include <cstring>
#include <omp.h>

static bool validate_utf8(const char *b, size_t length) {
  const unsigned char *bytes = (const unsigned char *)b;
  for (size_t index = 0;;) {
    if (index == length) {
      return true;
    }

    // Avoid a word load when the next byte already begins a multibyte sequence.
    if (bytes[index] < 0x80) {
      while (length - index >= sizeof(uint64_t)) {
        uint64_t word;
        std::memcpy(&word, bytes + index, sizeof(word));
        if ((word & UINT64_C(0x8080808080808080)) != 0) {
          break;
        }
        index += sizeof(word);
      }
      while (index < length && bytes[index] < 0x80) {
        ++index;
      }
      if (index == length) {
        return true;
      }
    }

    unsigned char byte1 = bytes[index++];
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
      if (index + 1 >= length) {
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
      if (index + 2 >= length) {
        return false;
      }
      int byte2 = bytes[index++];
      if ((byte2 & 0xC0) != 0x80
          // Check that 1 <= plane <= 16. Tricky optimized form of:
          // if (byte1 > (byte) 0xF4
          //     || byte1 == (byte) 0xF0 && byte2 < (byte) 0x90
          //     || byte1 == (byte) 0xF4 && byte2 > (byte) 0x8F)
          || (byte1 > 0xF4 || (byte1 == 0xF0 && byte2 < 0x90) || (byte1 == 0xF4 && byte2 > 0x8F))
          // Third byte trailing-byte test
          || (bytes[index++] & 0xC0) != 0x80
          // Fourth byte trailing-byte test
          || (bytes[index++] & 0xC0) != 0x80) {
        return false;
      }
    }
  }
}

extern "C" void run(const void* input1,const void* input2,void* output,int n,int parameter,int threads)
{*(uint32_t*)output=validate_utf8((const char*)input1,n);}
