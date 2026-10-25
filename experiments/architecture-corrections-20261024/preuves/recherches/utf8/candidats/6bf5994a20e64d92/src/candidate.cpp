#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <cstring>
#include <cstdint>
#include <cmath>
#include <algorithm>
#include <omp.h>

static bool validate_utf8(const char *b, size_t length) {
  const unsigned char *bytes = (const unsigned char *)b;
  size_t index = 0;

  while (index < length) {
    // Check complete scalar-sized words; never read beyond the input.
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

    const unsigned char lead = bytes[index++];
    if (lead < 0xC2 || lead > 0xF4) {
      return false;
    }

    unsigned int remaining = 1u + static_cast<unsigned int>(lead >= 0xE0) +
                             static_cast<unsigned int>(lead >= 0xF0);
    uint32_t lower = 0x80u +
                     (static_cast<uint32_t>(lead == 0xE0) << 5) +
                     (static_cast<uint32_t>(lead == 0xF0) << 4);
    uint32_t upper = 0xBFu -
                     (static_cast<uint32_t>(lead == 0xED) << 5) -
                     (static_cast<uint32_t>(lead == 0xF4) * 0x30u);

    while (remaining != 0) {
      if (index == length) {
        return false;
      }
      const uint32_t delta = static_cast<uint32_t>(bytes[index++]) - lower;
      if (delta > upper - lower) {
        return false;
      }
      lower = 0x80u;
      upper = 0xBFu;
      --remaining;
    }
  }

  return true;
}

extern "C" void run(const void *input1, const void *input2, void *output,
                    int n, int parameter, int threads) {
  *(uint32_t *)output = validate_utf8((const char *)input1, n);
}
