#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

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
          || (byte1 == 0xE0 && byte2 < 0xA0)
          || (byte1 == 0xED && 0xA0 <= byte2)
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

// Compress one selected bit from each of eight bytes into an 8-bit mask.
static inline uint8_t byte_bit_mask(uint64_t word, unsigned bit) {
  uint64_t lanes = (word >> bit) & UINT64_C(0x0101010101010101);
  lanes = (lanes | (lanes >> 7)) & UINT64_C(0x0003000300030003);
  lanes = (lanes | (lanes >> 14)) & UINT64_C(0x0000000F0000000F);
  lanes = (lanes | (lanes >> 28)) & UINT64_C(0x00000000000000FF);
  return (uint8_t)lanes;
}

static bool validate_utf8(const char *b, size_t length) {
  const unsigned char *bytes = (const unsigned char *)b;
  size_t index = 0;

  while (length - index >= 8) {
    // Assemble little-endian byte lanes without alignment or host-endian assumptions.
    const uint64_t word = (uint64_t)bytes[index]
        | ((uint64_t)bytes[index + 1] << 8)
        | ((uint64_t)bytes[index + 2] << 16)
        | ((uint64_t)bytes[index + 3] << 24)
        | ((uint64_t)bytes[index + 4] << 32)
        | ((uint64_t)bytes[index + 5] << 40)
        | ((uint64_t)bytes[index + 6] << 48)
        | ((uint64_t)bytes[index + 7] << 56);

    // Complete ASCII blocks require only the high-bit test.
    if ((word & UINT64_C(0x8080808080808080)) == 0) {
      index += 8;
      continue;
    }

    const uint8_t p0 = byte_bit_mask(word, 0);
    const uint8_t p1 = byte_bit_mask(word, 1);
    const uint8_t p2 = byte_bit_mask(word, 2);
    const uint8_t p3 = byte_bit_mask(word, 3);
    const uint8_t p4 = byte_bit_mask(word, 4);
    const uint8_t p5 = byte_bit_mask(word, 5);
    const uint8_t p6 = byte_bit_mask(word, 6);
    const uint8_t p7 = byte_bit_mask(word, 7);

    const uint8_t ascii = (uint8_t)~p7;
    const uint8_t continuation = (uint8_t)(p7 & (uint8_t)~p6);
    const uint8_t two_prefix = (uint8_t)(p7 & p6 & (uint8_t)~p5);
    const uint8_t three_prefix = (uint8_t)(p7 & p6 & p5 & (uint8_t)~p4);
    const uint8_t four_prefix = (uint8_t)(p7 & p6 & p5 & p4 & (uint8_t)~p3);

    const uint8_t invalid_two = (uint8_t)(two_prefix & (uint8_t)~(p4 | p3 | p2 | p1));
    const uint8_t lead2 = (uint8_t)(two_prefix & (uint8_t)~invalid_two);
    const uint8_t lead3 = three_prefix;
    const uint8_t invalid_four = (uint8_t)(four_prefix & p2 & (p1 | p0));
    const uint8_t lead4 = (uint8_t)(four_prefix & (uint8_t)~invalid_four);
    const uint8_t invalid = (uint8_t)~(ascii | continuation | lead2 | lead3 | lead4);
    if (invalid != 0) {
      return false;
    }

    // Defer a block whose final lanes may contain a sequence crossing its boundary.
    // The scalar control validates that block and the complete remaining suffix.
    if ((lead2 & 0x80u) != 0
        || (lead3 & 0xC0u) != 0
        || (lead4 & 0xE0u) != 0) {
      return validate_utf8_scalar((const char *)(bytes + index), length - index);
    }

    // For a self-contained block, leads must require exactly the continuation lanes present.
    const uint8_t starters = (uint8_t)(lead2 | lead3 | lead4);
    const uint8_t expected = (uint8_t)(
        (starters << 1)
        | ((lead3 | lead4) << 2)
        | (lead4 << 3));
    if (expected != continuation) {
      return false;
    }

    // E0/ED and F0/F4 have restricted second-byte ranges.
    const uint8_t e0 = (uint8_t)(lead3 & (uint8_t)~(p3 | p2 | p1 | p0));
    const uint8_t ed = (uint8_t)(lead3 & p3 & p2 & (uint8_t)~p1 & p0);
    const uint8_t f0 = (uint8_t)(lead4 & (uint8_t)~(p2 | p1 | p0));
    const uint8_t f4 = (uint8_t)(lead4 & p2 & (uint8_t)~p1 & (uint8_t)~p0);

    const uint8_t e0_second = (uint8_t)(e0 << 1);
    const uint8_t ed_second = (uint8_t)(ed << 1);
    const uint8_t f0_second = (uint8_t)(f0 << 1);
    const uint8_t f4_second = (uint8_t)(f4 << 1);
    if ((e0_second & (uint8_t)~p5) != 0
        || (ed_second & p5) != 0
        || (f0_second & (uint8_t)~p4) != 0
        || (f4_second & p4) != 0) {
      return false;
    }

    index += 8;
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
