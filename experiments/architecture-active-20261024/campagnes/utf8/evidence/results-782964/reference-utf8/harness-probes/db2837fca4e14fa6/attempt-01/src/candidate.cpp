#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

static bool validate_utf8(const char *b, size_t length) {
  const uint8_t *bytes = (const uint8_t *)b;
  size_t index = 0;

  while (index < length) {
    while (index < length && bytes[index] < 0x80) {
      ++index;
    }
    if (index == length) {
      return true;
    }

    const uint8_t lead = bytes[index++];
    if (lead < 0xc2 || lead > 0xf4) {
      return false;
    }

    const unsigned extra = 1u + (unsigned)(lead >= 0xe0) +
                           (unsigned)(lead >= 0xf0);
    if (length - index < extra) {
      return false;
    }

    const uint8_t second = bytes[index++];
    if ((second & 0xc0) != 0x80) {
      return false;
    }
    const bool bad_boundary =
        ((lead == 0xe0) & (second < 0xa0)) |
        ((lead == 0xed) & (second >= 0xa0)) |
        ((lead == 0xf0) & (second < 0x90)) |
        ((lead == 0xf4) & (second > 0x8f));
    if (bad_boundary) {
      return false;
    }

    for (unsigned remaining = extra - 1; remaining != 0; --remaining) {
      if ((bytes[index] & 0xc0) != 0x80) {
        return false;
      }
      ++index;
    }
  }

  return true;
}

extern "C" void run(const void *input1, const void *input2, void *output,
                    int n, int parameter, int threads) {
  *(uint32_t *)output = validate_utf8((const char *)input1, n);
}
