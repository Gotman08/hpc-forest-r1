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
      if (lead < 0xC2 || lead > 0xF4) {
        return false;
      }

      // Derive continuation count and first-byte bounds from predicates.
      remaining = 1u + static_cast<unsigned>(lead >= 0xE0) +
                  static_cast<unsigned>(lead >= 0xF0);
      next_min = static_cast<unsigned char>(
          0x80u + static_cast<unsigned>(lead == 0xE0) * 0x20u +
          static_cast<unsigned>(lead == 0xF0) * 0x10u);
      next_max = static_cast<unsigned char>(
          0xBFu - static_cast<unsigned>(lead == 0xED) * 0x20u -
          static_cast<unsigned>(lead == 0xF4) * 0x30u);

      if (index == length) {
        return false;
      }
    }

    const unsigned value = bytes[index++];
    const unsigned minimum = next_min;
    const unsigned maximum = next_max;
    if (value - minimum > maximum - minimum) {
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
