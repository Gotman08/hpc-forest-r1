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

#define REPEAT_16(value) value, value, value, value, value, value, value, value, value, value, value, value, value, value, value, value
#define REPEAT_8(value) value, value, value, value, value, value, value, value
#define REPEAT_4(value) value, value, value, value
#define REPEAT_3(value) value, value, value
#define REPEAT_2(value) value, value

  // Each row is a DFA state and each column is an input byte.
  // Restricted first-continuation states encode E0, ED, F0, and F4 limits.
  static const unsigned char transition[9][256] = {
    {
      REPEAT_16(ACCEPT), REPEAT_16(ACCEPT), REPEAT_16(ACCEPT), REPEAT_16(ACCEPT),
      REPEAT_16(ACCEPT), REPEAT_16(ACCEPT), REPEAT_16(ACCEPT), REPEAT_16(ACCEPT),
      REPEAT_16(REJECT), REPEAT_16(REJECT), REPEAT_16(REJECT), REPEAT_16(REJECT),
      REJECT, REJECT, REPEAT_8(EXPECT_ONE), REPEAT_4(EXPECT_ONE), REPEAT_2(EXPECT_ONE),
      REPEAT_16(EXPECT_ONE),
      E0_FIRST, REPEAT_8(EXPECT_TWO), REPEAT_4(EXPECT_TWO), ED_FIRST, REPEAT_2(EXPECT_TWO),
      F0_FIRST, REPEAT_3(EXPECT_THREE), F4_FIRST, REPEAT_8(REJECT), REPEAT_3(REJECT)
    },
    {
      REPEAT_16(REJECT), REPEAT_16(REJECT), REPEAT_16(REJECT), REPEAT_16(REJECT),
      REPEAT_16(REJECT), REPEAT_16(REJECT), REPEAT_16(REJECT), REPEAT_16(REJECT),
      REPEAT_16(ACCEPT), REPEAT_16(ACCEPT), REPEAT_16(ACCEPT), REPEAT_16(ACCEPT),
      REPEAT_16(REJECT), REPEAT_16(REJECT), REPEAT_16(REJECT), REPEAT_16(REJECT)
    },
    {
      REPEAT_16(REJECT), REPEAT_16(REJECT), REPEAT_16(REJECT), REPEAT_16(REJECT),
      REPEAT_16(REJECT), REPEAT_16(REJECT), REPEAT_16(REJECT), REPEAT_16(REJECT),
      REPEAT_16(EXPECT_ONE), REPEAT_16(EXPECT_ONE), REPEAT_16(EXPECT_ONE), REPEAT_16(EXPECT_ONE),
      REPEAT_16(REJECT), REPEAT_16(REJECT), REPEAT_16(REJECT), REPEAT_16(REJECT)
    },
    {
      REPEAT_16(REJECT), REPEAT_16(REJECT), REPEAT_16(REJECT), REPEAT_16(REJECT),
      REPEAT_16(REJECT), REPEAT_16(REJECT), REPEAT_16(REJECT), REPEAT_16(REJECT),
      REPEAT_16(REJECT), REPEAT_16(REJECT),
      REPEAT_16(EXPECT_ONE), REPEAT_16(EXPECT_ONE),
      REPEAT_16(REJECT), REPEAT_16(REJECT), REPEAT_16(REJECT), REPEAT_16(REJECT)
    },
    {
      REPEAT_16(REJECT), REPEAT_16(REJECT), REPEAT_16(REJECT), REPEAT_16(REJECT),
      REPEAT_16(REJECT), REPEAT_16(REJECT), REPEAT_16(REJECT), REPEAT_16(REJECT),
      REPEAT_16(EXPECT_ONE), REPEAT_16(EXPECT_ONE),
      REPEAT_4(REJECT), REPEAT_2(REJECT)
    },
    {
      REPEAT_16(REJECT), REPEAT_16(REJECT), REPEAT_16(REJECT), REPEAT_16(REJECT),
      REPEAT_16(REJECT), REPEAT_16(REJECT), REPEAT_16(REJECT), REPEAT_16(REJECT),
      REPEAT_16(EXPECT_TWO), REPEAT_16(EXPECT_TWO), REPEAT_16(EXPECT_TWO), REPEAT_16(EXPECT_TWO),
      REPEAT_16(REJECT), REPEAT_16(REJECT), REPEAT_16(REJECT), REPEAT_16(REJECT)
    },
    {
      REPEAT_16(REJECT), REPEAT_16(REJECT), REPEAT_16(REJECT), REPEAT_16(REJECT),
      REPEAT_16(REJECT), REPEAT_16(REJECT), REPEAT_16(REJECT), REPEAT_16(REJECT),
      REPEAT_16(REJECT),
      REPEAT_16(EXPECT_TWO), REPEAT_16(EXPECT_TWO), REPEAT_16(EXPECT_TWO),
      REPEAT_16(REJECT), REPEAT_16(REJECT), REPEAT_16(REJECT), REPEAT_16(REJECT)
    },
    {
      REPEAT_16(REJECT), REPEAT_16(REJECT), REPEAT_16(REJECT), REPEAT_16(REJECT),
      REPEAT_16(REJECT), REPEAT_16(REJECT), REPEAT_16(REJECT), REPEAT_16(REJECT),
      REPEAT_16(EXPECT_TWO),
      REPEAT_4(REJECT), REPEAT_3(REJECT)
    },
    {
      REPEAT_16(REJECT), REPEAT_16(REJECT), REPEAT_16(REJECT), REPEAT_16(REJECT),
      REPEAT_16(REJECT), REPEAT_16(REJECT), REPEAT_16(REJECT), REPEAT_16(REJECT),
      REPEAT_16(REJECT), REPEAT_16(REJECT), REPEAT_16(REJECT), REPEAT_16(REJECT),
      REPEAT_16(REJECT), REPEAT_16(REJECT), REPEAT_16(REJECT), REPEAT_16(REJECT)
    }
  };

#undef REPEAT_16
#undef REPEAT_8
#undef REPEAT_4
#undef REPEAT_3
#undef REPEAT_2

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
      state = transition[state][bytes[index++]];
    } while (index < length && state != ACCEPT && state != REJECT);

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
