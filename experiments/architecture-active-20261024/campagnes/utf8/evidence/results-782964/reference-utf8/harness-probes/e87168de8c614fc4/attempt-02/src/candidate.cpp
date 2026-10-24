#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

static bool validate_utf8(const char *b, size_t length) {
  const uint8_t *bytes = (const uint8_t *)b;
  size_t index = 0;

  for (;;) {
    while (index < length && bytes[index] < 0x80) {
      ++index;
    }
    if (index == length) {
      return true;
    }

    const uint8_t lead = bytes[index++];
    if (lead < 0xc2) {
      return false;
    }

    if (lead < 0xe0) {
      if (length - index < 1 || (bytes[index] & 0xc0) != 0x80) {
        return false;
      }
      ++index;
      continue;
    }

    if (lead < 0xf0) {
      if (length - index < 2) {
        return false;
      }
      const uint8_t second = bytes[index];
      const uint8_t third = bytes[index + 1];
      if ((second & 0xc0) != 0x80 || (third & 0xc0) != 0x80 ||
          (lead == 0xe0 && second < 0xa0) ||
          (lead == 0xed && second >= 0xa0)) {
        return false;
      }
      index += 2;
      continue;
    }

    if (lead <= 0xf4) {
      if (length - index < 3) {
        return false;
      }
      const uint8_t second = bytes[index];
      const uint8_t third = bytes[index + 1];
      const uint8_t fourth = bytes[index + 2];
      if ((second & 0xc0) != 0x80 || (third & 0xc0) != 0x80 ||
          (fourth & 0xc0) != 0x80 ||
          (lead == 0xf0 && second < 0x90) ||
          (lead == 0xf4 && second > 0x8f)) {
        return false;
      }
      index += 3;
      continue;
    }

    return false;
  }
}

extern "C" void run(const void *input1, const void *input2, void *output,
                    int n, int parameter, int threads) {
  *(uint32_t *)output = validate_utf8((const char *)input1, n);
}
