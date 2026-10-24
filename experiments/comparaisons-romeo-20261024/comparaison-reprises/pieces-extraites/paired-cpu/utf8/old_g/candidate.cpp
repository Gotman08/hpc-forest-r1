#include <cstddef>
#include <cstdint>
#include <emmintrin.h>

static inline uint32_t mask_of(__m128i value) {
  return static_cast<uint32_t>(_mm_movemask_epi8(value)) & 0xffffu;
}

static bool validate_utf8_block(const unsigned char *data,
                                unsigned char previous_byte, int &pending) {
  const __m128i value =
      _mm_loadu_si128(reinterpret_cast<const __m128i *>(data));
  const __m128i zero = _mm_setzero_si128();
  const uint32_t sign_bits = mask_of(value);

  // Keep the common ASCII case to one load and a mask test. A block cannot
  // take this path when it must finish a sequence begun in the prior block.
  if (sign_bits == 0 && pending == 0) {
    return true;
  }

  const __m128i continuation = _mm_cmpeq_epi8(
      _mm_and_si128(value, _mm_set1_epi8(-64)), _mm_set1_epi8(-128));
  const __m128i two_byte = _mm_and_si128(
      _mm_cmpgt_epi8(value, _mm_set1_epi8(-63)),
      _mm_cmpgt_epi8(_mm_set1_epi8(-32), value));
  const __m128i three_byte = _mm_and_si128(
      _mm_cmpgt_epi8(value, _mm_set1_epi8(-33)),
      _mm_cmpgt_epi8(_mm_set1_epi8(-16), value));
  const __m128i four_byte = _mm_and_si128(
      _mm_cmpgt_epi8(value, _mm_set1_epi8(-17)),
      _mm_cmpgt_epi8(_mm_set1_epi8(-11), value));

  const uint32_t continuation_bits = mask_of(continuation);
  const uint32_t two_bits = mask_of(two_byte);
  const uint32_t three_bits = mask_of(three_byte);
  const uint32_t four_bits = mask_of(four_byte);
  const uint32_t ascii_bits = (~sign_bits) & 0xffffu;
  const uint32_t allowed = ascii_bits | continuation_bits | two_bits |
                           three_bits | four_bits;
  if (allowed != 0xffffu) {
    return false;
  }

  // Construct the exact continuation-byte positions in a scalar bit mask.
  // Bits above lane 15 are the continuation debt carried to the next block.
  if (pending < 0 || pending > 3) {
    return false;
  }
  const uint32_t leads = two_bits | three_bits | four_bits;
  uint32_t expected = (leads << 1) |
                      ((three_bits | four_bits) << 2) | (four_bits << 3);
  if (pending != 0) {
    expected |= (uint32_t{1} << pending) - 1u;
  }
  if ((expected & 0xffffu) != continuation_bits) {
    return false;
  }

  const uint32_t carry = expected >> 16;
  if (carry == 0) {
    pending = 0;
  } else if (carry == 1) {
    pending = 1;
  } else if (carry == 3) {
    pending = 2;
  } else if (carry == 7) {
    pending = 3;
  } else {
    return false;
  }

  // Enforce restricted second-byte ranges only when a restricted lead byte
  // precedes a lane in this block (including across the block boundary).
  const __m128i previous = _mm_or_si128(
      _mm_slli_si128(value, 1),
      _mm_cvtsi32_si128(static_cast<int>(previous_byte)));
  const uint32_t after_e0 =
      mask_of(_mm_cmpeq_epi8(previous, _mm_set1_epi8(-32)));
  const uint32_t after_ed =
      mask_of(_mm_cmpeq_epi8(previous, _mm_set1_epi8(-19)));
  const uint32_t after_f0 =
      mask_of(_mm_cmpeq_epi8(previous, _mm_set1_epi8(-16)));
  const uint32_t after_f4 =
      mask_of(_mm_cmpeq_epi8(previous, _mm_set1_epi8(-12)));
  if ((after_e0 | after_ed | after_f0 | after_f4) == 0) {
    return true;
  }

  const uint32_t has_bit_20 = mask_of(_mm_cmpeq_epi8(
      _mm_and_si128(value, _mm_set1_epi8(0x20)), _mm_set1_epi8(0x20)));
  const uint32_t has_no_bits_70 = mask_of(_mm_cmpeq_epi8(
      _mm_and_si128(value, _mm_set1_epi8(0x70)), zero));
  const uint32_t bad_restriction =
      (after_e0 & ~has_bit_20) | (after_ed & has_bit_20) |
      (after_f0 & has_no_bits_70) | (after_f4 & ~has_no_bits_70);
  return (bad_restriction & 0xffffu) == 0;
}

static bool validate_utf8_tail(const unsigned char *bytes, size_t length,
                               int &pending, unsigned char &previous_byte) {
  for (size_t i = 0; i < length; ++i) {
    const unsigned char byte = bytes[i];
    if (pending != 0) {
      if ((byte & 0xc0u) != 0x80u) {
        return false;
      }
      if ((previous_byte == 0xe0u && byte < 0xa0u) ||
          (previous_byte == 0xedu && byte > 0x9fu) ||
          (previous_byte == 0xf0u && byte < 0x90u) ||
          (previous_byte == 0xf4u && byte > 0x8fu)) {
        return false;
      }
      --pending;
    } else if (byte <= 0x7fu) {
      // ASCII byte.
    } else if (byte >= 0xc2u && byte <= 0xdfu) {
      pending = 1;
    } else if (byte >= 0xe0u && byte <= 0xefu) {
      pending = 2;
    } else if (byte >= 0xf0u && byte <= 0xf4u) {
      pending = 3;
    } else {
      return false;
    }
    previous_byte = byte;
  }
  return true;
}

static bool validate_utf8(const char *buffer, size_t length) {
  const unsigned char *bytes = reinterpret_cast<const unsigned char *>(buffer);
  size_t index = 0;
  int pending = 0;
  unsigned char previous_byte = 0;

  while (length - index >= 16) {
    if (!validate_utf8_block(bytes + index, previous_byte, pending)) {
      return false;
    }
    previous_byte = bytes[index + 15];
    index += 16;
  }

  if (!validate_utf8_tail(bytes + index, length - index, pending,
                          previous_byte)) {
    return false;
  }
  return pending == 0;
}

extern "C" void run(const void *input1, const void *input2, void *output,
                    int n, int parameter, int threads) {
  *static_cast<uint32_t *>(output) =
      validate_utf8(static_cast<const char *>(input1), static_cast<size_t>(n));
}
