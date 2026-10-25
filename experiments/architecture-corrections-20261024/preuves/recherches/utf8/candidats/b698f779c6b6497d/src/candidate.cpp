#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

static bool validate_utf8(const char *b, size_t length) {
  const unsigned char *bytes = (const unsigned char *)b;

  enum State {
    ACCEPT = 0,
    EXPECT_ONE,
    EXPECT_TWO,
    E0_FIRST,
    ED_FIRST,
    EXPECT_THREE,
    F0_FIRST,
    F4_FIRST,
    REJECT
  };

  // Classes: ASCII, 80-8F, 90-9F, A0-BF, C2-DF, E0,
  // E1-EC or EE-EF, ED, F0, F1-F3, F4, invalid.
  static const unsigned char byte_class[256] = {
    0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,
    0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,
    0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,
    0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,
    0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,
    0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,
    0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,
    0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,
    1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,
    2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,
    3,3,3,3,3,3,3,3,3,3,3,3,3,3,3,3,
    3,3,3,3,3,3,3,3,3,3,3,3,3,3,3,3,
    11,11,4,4,4,4,4,4,4,4,4,4,4,4,4,4,
    4,4,4,4,4,4,4,4,4,4,4,4,4,4,4,4,
    5,6,6,6,6,6,6,6,6,6,6,6,6,7,6,6,
    8,9,9,9,10,11,11,11,11,11,11,11,11,11,11,11
  };

  // The reject state is absorbing. The remaining states encode how many
  // continuations remain and the restricted first continuation where needed.
  static const unsigned char transition[9][12] = {
    {ACCEPT, REJECT, REJECT, REJECT, EXPECT_ONE, E0_FIRST, EXPECT_TWO,
     ED_FIRST, F0_FIRST, EXPECT_THREE, F4_FIRST, REJECT},
    {REJECT, ACCEPT, ACCEPT, ACCEPT, REJECT, REJECT, REJECT,
     REJECT, REJECT, REJECT, REJECT, REJECT},
    {REJECT, EXPECT_ONE, EXPECT_ONE, EXPECT_ONE, REJECT, REJECT, REJECT,
     REJECT, REJECT, REJECT, REJECT, REJECT},
    {REJECT, REJECT, REJECT, EXPECT_ONE, REJECT, REJECT, REJECT,
     REJECT, REJECT, REJECT, REJECT, REJECT},
    {REJECT, EXPECT_ONE, EXPECT_ONE, REJECT, REJECT, REJECT, REJECT,
     REJECT, REJECT, REJECT, REJECT, REJECT},
    {REJECT, EXPECT_TWO, EXPECT_TWO, EXPECT_TWO, REJECT, REJECT, REJECT,
     REJECT, REJECT, REJECT, REJECT, REJECT},
    {REJECT, REJECT, EXPECT_TWO, EXPECT_TWO, REJECT, REJECT, REJECT,
     REJECT, REJECT, REJECT, REJECT, REJECT},
    {REJECT, EXPECT_TWO, REJECT, REJECT, REJECT, REJECT, REJECT,
     REJECT, REJECT, REJECT, REJECT, REJECT},
    {REJECT, REJECT, REJECT, REJECT, REJECT, REJECT, REJECT,
     REJECT, REJECT, REJECT, REJECT, REJECT}
  };

  size_t index = 0;
  while (index < length) {
    // Keep the common ASCII run on a simple scalar scan.
    while (index < length && bytes[index] < 0x80) {
      ++index;
    }
    if (index == length) {
      return true;
    }

    unsigned char state = ACCEPT;
    do {
      state = transition[state][byte_class[bytes[index++]]];
    } while (index < length && state != ACCEPT);

    if (state != ACCEPT) {
      return false;
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
