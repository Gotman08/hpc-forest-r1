#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

// Byte classes: ASCII, three continuation ranges, legal lead ranges, invalid.
static const uint8_t byte_class[256] = {
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
  12, 12, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4,
  4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4,
  5, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 7, 8, 8,
  9, 10, 10, 10, 11, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12
};

// State 8 is the rejecting sink. State 0 is the accepting boundary.
static const uint8_t transition[8][13] = {
  {0, 8, 8, 8, 1, 3, 2, 4, 2, 6, 5, 7, 8},
  {8, 0, 0, 0, 8, 8, 8, 8, 8, 8, 8, 8, 8},
  {8, 1, 1, 1, 8, 8, 8, 8, 8, 8, 8, 8, 8},
  {8, 8, 8, 1, 8, 8, 8, 8, 8, 8, 8, 8, 8},
  {8, 1, 1, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8},
  {8, 2, 2, 2, 8, 8, 8, 8, 8, 8, 8, 8, 8},
  {8, 8, 2, 2, 8, 8, 8, 8, 8, 8, 8, 8, 8},
  {8, 1, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8}
};

static bool validate_utf8(const char *b, size_t length) {
  const uint8_t *bytes = (const uint8_t *)b;
  size_t index = 0;

  for (;;) {
    // Preserve the ASCII run fast path; use the DFA for non-ASCII bytes.
    while (index < length && bytes[index] < 0x80) {
      ++index;
    }
    if (index == length) {
      return true;
    }

    uint8_t state = transition[0][byte_class[bytes[index++]]];
    if (state == 8) {
      return false;
    }
    while (state != 0) {
      if (index == length) {
        return false;
      }
      state = transition[state][byte_class[bytes[index++]]];
      if (state == 8) {
        return false;
      }
    }
  }
}

extern "C" void run(const void *input1, const void *input2, void *output,
                    int n, int parameter, int threads) {
  *(uint32_t *)output = validate_utf8((const char *)input1, n);
}
