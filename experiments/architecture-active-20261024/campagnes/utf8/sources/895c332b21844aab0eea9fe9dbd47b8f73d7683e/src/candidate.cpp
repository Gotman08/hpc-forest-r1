#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
static bool validate_utf8(const char *b, size_t length) {
  static const unsigned char byte_class[256] = {
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
    2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2,
    3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3,
    3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3,
    11, 11, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4,
    4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4,
    5, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 7, 6, 6,
    8, 9, 9, 9, 10, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11
  };
  static const unsigned char transition[8][12] = {
    {0, 8, 8, 8, 1, 4, 2, 5, 6, 3, 7, 8},
    {8, 0, 0, 0, 8, 8, 8, 8, 8, 8, 8, 8},
    {8, 1, 1, 1, 8, 8, 8, 8, 8, 8, 8, 8},
    {8, 2, 2, 2, 8, 8, 8, 8, 8, 8, 8, 8},
    {8, 8, 8, 1, 8, 8, 8, 8, 8, 8, 8, 8},
    {8, 1, 1, 8, 8, 8, 8, 8, 8, 8, 8, 8},
    {8, 8, 2, 2, 8, 8, 8, 8, 8, 8, 8, 8},
    {8, 2, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8}
  };
  const unsigned char *bytes = (const unsigned char *)b;
  unsigned char state = 0;

  for (size_t index = 0; index < length;) {
    if (state == 0 && bytes[index] < 0x80) {
      do {
        ++index;
      } while (index < length && bytes[index] < 0x80);
      continue;
    }

    state = transition[state][byte_class[bytes[index++]]];
    if (state == 8) {
      return false;
    }
  }
  return state == 0;
}
#include <cstdint>
#include <cstring>
#include <cmath>
#include <algorithm>
#include <omp.h>
extern "C" void run(const void* input1,const void* input2,void* output,int n,int parameter,int threads)
{*(uint32_t*)output=validate_utf8((const char*)input1,n);}
