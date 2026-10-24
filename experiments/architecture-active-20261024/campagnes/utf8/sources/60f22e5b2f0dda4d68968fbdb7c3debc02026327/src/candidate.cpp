#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <string.h>

static bool validate_utf8_scalar(const char *b, size_t length) {
  const unsigned char *bytes = (const unsigned char *)b;
  for (size_t index = 0;;) {
    unsigned char byte1;

    do { // fast ASCII Path
      if (index >= length) {
        return true;
      }
      byte1 = bytes[index++];
    } while (byte1 < 0x80);
    if (byte1 < 0xE0) {
      // Two-byte form.
      if (index == length) {
        return false;
      }
      if (byte1 < 0xC2 || (bytes[index++] & 0xC0) != 0x80) {
        return false;
      }
    } else if (byte1 < 0xF0) {
      // Three-byte form.
      if (index + 1 >= length) {
        return false;
      }
      unsigned char byte2 = bytes[index++];
      if ((byte2 & 0xC0) != 0x80
          // Overlong? 5 most significant bits must not all be zero.
          || (byte1 == 0xE0 && byte2 < 0xA0)
          // Check for illegal surrogate codepoints.
          || (byte1 == 0xED && 0xA0 <= byte2)
          // Third byte trailing-byte test.
          || (bytes[index++] & 0xC0) != 0x80) {
        return false;
      }
    } else {
      // Four-byte form.
      if (index + 2 >= length) {
        return false;
      }
      int byte2 = bytes[index++];
      if ((byte2 & 0xC0) != 0x80
          || (byte1 > 0xF4 || (byte1 == 0xF0 && byte2 < 0x90) || (byte1 == 0xF4 && byte2 > 0x8F))
          || (bytes[index++] & 0xC0) != 0x80
          || (bytes[index++] & 0xC0) != 0x80) {
        return false;
      }
    }
  }
}

static inline bool decode_utf8_one(const unsigned char *bytes, size_t length,
                                   size_t *index) {
  const unsigned char byte1 = bytes[(*index)++];
  if (byte1 < 0x80) {
    return true;
  }
  if (byte1 < 0xE0) {
    if (byte1 < 0xC2 || length - *index < 1) {
      return false;
    }
    return (bytes[(*index)++] & 0xC0) == 0x80;
  }
  if (byte1 < 0xF0) {
    if (length - *index < 2) {
      return false;
    }
    const unsigned char byte2 = bytes[(*index)++];
    if ((byte2 & 0xC0) != 0x80
        || (byte1 == 0xE0 && byte2 < 0xA0)
        || (byte1 == 0xED && byte2 >= 0xA0)
        || (bytes[(*index)++] & 0xC0) != 0x80) {
      return false;
    }
    return true;
  }
  if (length - *index < 3) {
    return false;
  }
  const unsigned char byte2 = bytes[(*index)++];
  if ((byte2 & 0xC0) != 0x80
      || byte1 > 0xF4
      || (byte1 == 0xF0 && byte2 < 0x90)
      || (byte1 == 0xF4 && byte2 > 0x8F)
      || (bytes[(*index)++] & 0xC0) != 0x80
      || (bytes[(*index)++] & 0xC0) != 0x80) {
    return false;
  }
  return true;
}

static bool validate_utf8(const char *b, size_t length) {
  const unsigned char *bytes = (const unsigned char *)b;
  size_t index = 0;
  const uint64_t high_bits = UINT64_C(0x8080808080808080);

  while (length - index >= 8) {
    uint64_t word;
    memcpy(&word, bytes + index, sizeof(word));
    if ((word & high_bits) == 0) {
      index += 8;
      continue;
    }

    // Decode a mixed block through its end, keeping the next block boundary
    // at a complete code point rather than carrying partial UTF-8 state.
    const size_t block_end = index + 8;
    do {
      if (!decode_utf8_one(bytes, length, &index)) {
        return false;
      }
    } while (index < block_end);
  }

  if (index == length) {
    return true;
  }
  return validate_utf8_scalar((const char *)(bytes + index), length - index);
}

#include <cstdint>
#include <cstring>
#include <cmath>
#include <algorithm>
#include <omp.h>
extern "C" void run(const void* input1,const void* input2,void* output,int n,int parameter,int threads)
{*(uint32_t*)output=validate_utf8((const char*)input1,n);}
