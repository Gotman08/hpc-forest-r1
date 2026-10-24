#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
static bool validate_utf8(const char *b, size_t length) {
  const unsigned char *bytes = (const unsigned char *)b;
  for (size_t index = 0;;) {
    unsigned char byte1;

    do { // fast ASCII Path
      if (index >= length) {
        return true;
      }
      byte1 = bytes[index++];
    } while (byte1 < 0x80);
    if (byte1 < 0xE0) {
      // Two-byte form.
      if (index == length) {
        return false;
      }
      if (byte1 < 0xC2 || bytes[index++] > 0xBF) {
        return false;
      }
    } else if (byte1 < 0xF0) {
      // Three-byte form.
      if (index + 1 >= length) {
        return false;
      }
      unsigned char byte2 = bytes[index++];
      if (byte2 > 0xBF
          // Overlong? 5 most significant bits must not all be zero.
          || (byte1 == 0xE0 && byte2 < 0xA0)
          // Check for illegal surrogate codepoints.
          || (byte1 == 0xED && 0xA0 <= byte2)
          // Third byte trailing-byte test.
          || bytes[index++] > 0xBF) {
        return false;
      }
    } else {

      // Four-byte form.
      if (index + 2 >= length) {
        return false;
      }
      int byte2 = bytes[index++];
      if (byte2 > 0xBF
          // Check that 1 <= plane <= 16. Tricky optimized form of:
          // if (byte1 > (byte) 0xF4
          //     || byte1 == (byte) 0xF0 && byte2 < (byte) 0x90
          //     || byte1 == (byte) 0xF4 && byte2 > (byte) 0x8F)
          || (((byte1 << 28) + (byte2 - 0x90)) >> 30) != 0
          // Third byte trailing-byte test
          || bytes[index++] > 0xBF
          // Fourth byte trailing-byte test
          || bytes[index++] > 0xBF) {
        return false;
      }
    }
  }
}
#include <cstdint>
#include <cstring>
#include <cmath>
#include <algorithm>
#include <omp.h>
extern "C" void run(const void* input1,const void* input2,void* output,int n,int parameter,int threads)
{*(uint32_t*)output=validate_utf8((const char*)input1,n);}
