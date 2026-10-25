#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

static bool validate_utf8(const char *b, size_t length) {
  static constexpr unsigned char continuation_count_by_nibble[16] = {
      0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 2, 3};
  const unsigned char *bytes = (const unsigned char *)b;
  size_t index = 0;

  while (index < length) {
    // Skip ASCII in a run; classify only bytes that can begin a multibyte sequence.
    while (index < length && bytes[index] < 0x80) {
      ++index;
    }
    if (index == length) {
      return true;
    }

    const unsigned char lead = bytes[index++];
    const unsigned continuation_count = continuation_count_by_nibble[lead >> 4];
    if (continuation_count == 0 || lead < 0xC2 || lead > 0xF4) {
      return false;
    }
    if (index == length) {
      return false;
    }

    // Encode the E0, ED, F0, and F4 second-byte restrictions as arithmetic bounds.
    const unsigned lower_adjustment =
        static_cast<unsigned>(lead == 0xE0) * 0x20u +
        static_cast<unsigned>(lead == 0xF0) * 0x10u;
    const unsigned upper_adjustment =
        static_cast<unsigned>(lead == 0xED) * 0x20u +
        static_cast<unsigned>(lead == 0xF4) * 0x30u;
    const unsigned char first_min =
        static_cast<unsigned char>(0x80u + lower_adjustment);
    const unsigned char first_max =
        static_cast<unsigned char>(0xBFu - upper_adjustment);

    const unsigned char first_continuation = bytes[index++];
    if (static_cast<unsigned>(first_continuation - first_min) >
        static_cast<unsigned>(first_max - first_min)) {
      return false;
    }

    for (unsigned remaining = continuation_count - 1; remaining != 0;
         --remaining) {
      if (index == length) {
        return false;
      }
      const unsigned char continuation = bytes[index++];
      if ((continuation & 0xC0u) != 0x80u) {
        return false;
      }
    }
  }

  return true;
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
