#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

static bool validate_utf8(const char *b, size_t length) {
  const unsigned char *bytes = (const unsigned char *)b;
  size_t index = 0;
  unsigned remaining = 0;
  unsigned char next_min = 0x80;
  unsigned char next_max = 0xBF;

  while (index < length) {
    if (remaining == 0) {
      // Consume ordinary ASCII without entering the lead-byte classifier.
      while (index < length && bytes[index] < 0x80) {
        ++index;
      }
      if (index == length) {
        return true;
      }

      const unsigned char lead = bytes[index++];
      next_min = 0x80;
      next_max = 0xBF;
      if (lead < 0xE0) {
        if (lead < 0xC2) {
          return false;
        }
        remaining = 1;
      } else if (lead < 0xF0) {
        remaining = 2;
        if (lead == 0xE0) {
          next_min = 0xA0;
        } else if (lead == 0xED) {
          next_max = 0x9F;
        }
      } else if (lead <= 0xF4) {
        remaining = 3;
        if (lead == 0xF0) {
          next_min = 0x90;
        } else if (lead == 0xF4) {
          next_max = 0x8F;
        }
      } else {
        return false;
      }

      if (index == length) {
        return false;
      }
    }

    const unsigned char continuation = bytes[index++];
    if (continuation < next_min || continuation > next_max) {
      return false;
    }
    --remaining;
    next_min = 0x80;
    next_max = 0xBF;
  }

  return remaining == 0;
}

#include <cstdint>
#include <cstring>
#include <cmath>
#include <algorithm>
#include <omp.h>

extern "C" void run(const void *input1, const void *input2, void *output,
                    int n, int parameter, int threads) {
  *(uint32_t *)output = validate_utf8((const char *)input1, n);
}
