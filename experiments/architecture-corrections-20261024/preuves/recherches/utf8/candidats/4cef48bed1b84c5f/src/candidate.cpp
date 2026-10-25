#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

static bool validate_utf8(const char *b, size_t length) {
  const unsigned char *bytes = (const unsigned char *)b;
  unsigned int remaining = 0;
  unsigned int lower = 0x80u;
  unsigned int upper = 0xBFu;

  // Keep continuation requirements in registers and visit each byte once.
  for (size_t index = 0; index < length; ++index) {
    const unsigned int byte = bytes[index];

    if (remaining != 0) {
      if ((byte - lower) > (upper - lower)) {
        return false;
      }
      --remaining;
      lower = 0x80u;
      upper = 0xBFu;
      continue;
    }

    if (byte < 0x80u) {
      continue;
    }
    if (byte < 0xC2u || byte > 0xF4u) {
      return false;
    }

    // Valid lead ranges encode one, two, or three following continuations.
    remaining = 1u + (byte >= 0xE0u) + (byte >= 0xF0u);

    // Tighten only the first continuation range for E0, ED, F0, and F4.
    const unsigned int is_e0 = (byte == 0xE0u);
    const unsigned int is_ed = (byte == 0xEDu);
    const unsigned int is_f0 = (byte == 0xF0u);
    const unsigned int is_f4 = (byte == 0xF4u);
    lower = 0x80u + is_e0 * 0x20u + is_f0 * 0x10u;
    upper = 0xBFu - is_ed * 0x20u - is_f4 * 0x30u;
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
