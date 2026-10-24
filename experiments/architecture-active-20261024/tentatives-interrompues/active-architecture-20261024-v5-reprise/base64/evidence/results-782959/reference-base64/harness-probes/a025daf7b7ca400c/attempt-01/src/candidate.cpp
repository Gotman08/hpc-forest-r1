#ifndef SCALAR_B64
#define SCALAR_B64

#include <stddef.h>
#include <stdint.h>
#include <string.h>

#ifdef __cplusplus
extern "C" {
#endif

int scalar_base64_decode(const char *src, size_t srclen, char *out, size_t *outlen);
void scalar_base64_encode(const char *src, size_t srclen, char *out, size_t *outlen);

#ifdef __cplusplus
}
#endif

static inline int base64_value(uint8_t c, uint8_t *value) {
  if (c >= 'A' && c <= 'Z') {
    *value = (uint8_t)(c - 'A');
  } else if (c >= 'a' && c <= 'z') {
    *value = (uint8_t)(c - 'a' + 26);
  } else if (c >= '0' && c <= '9') {
    *value = (uint8_t)(c - '0' + 52);
  } else if (c == '+') {
    *value = 62;
  } else if (c == '/') {
    *value = 63;
  } else {
    return 0;
  }
  return 1;
}

static inline uint64_t base64_expand_byte_lane_mask(uint64_t flags) {
  return flags | (flags - (flags >> 7));
}

static inline int base64_decode8_swar(uint64_t word, uint8_t *out) {
  const uint64_t byte_high = 0x8080808080808080ULL;
  const uint64_t byte_low5 = 0x1f1f1f1f1f1f1f1fULL;
  const uint64_t byte_bit5 = 0x2020202020202020ULL;

  if ((word & byte_high) != 0) {
    return 0;
  }

  const uint64_t folded = word & 0xdfdfdfdfdfdfdfdfULL;
  const uint64_t ge_letter_a =
      ((folded | byte_high) - 0x4141414141414141ULL) & byte_high;
  const uint64_t ge_after_letter_z =
      ((folded | byte_high) - 0x5b5b5b5b5b5b5b5bULL) & byte_high;
  const uint64_t letters = ge_letter_a & ~ge_after_letter_z;
  const uint64_t ge_digit_zero =
      ((word | byte_high) - 0x3030303030303030ULL) & byte_high;
  const uint64_t ge_after_digit_nine =
      ((word | byte_high) - 0x3a3a3a3a3a3a3a3aULL) & byte_high;
  const uint64_t digits = ge_digit_zero & ~ge_after_digit_nine;
  const uint64_t special_diff =
      (word & 0xf3f3f3f3f3f3f3f3ULL) ^ 0x2323232323232323ULL;
  const uint64_t special_nonzero =
      ((special_diff | byte_high) - 0x0101010101010101ULL) & byte_high;
  const uint64_t specials = byte_high & ~special_nonzero;

  if ((letters | digits | specials) != byte_high) {
    return 0;
  }

  const uint64_t letter_mask = base64_expand_byte_lane_mask(letters);
  const uint64_t digit_mask = base64_expand_byte_lane_mask(digits);
  const uint64_t special_mask = base64_expand_byte_lane_mask(specials);
  const uint64_t lower_flags = ((word & byte_bit5) << 2) & letters;
  const uint64_t lower_mask = base64_expand_byte_lane_mask(lower_flags);
  const uint64_t letter_base = ((word & byte_low5) + byte_low5) & byte_low5;
  const uint64_t letter_values = letter_base +
      (lower_mask & 0x1a1a1a1a1a1a1a1aULL);
  const uint64_t digit_values =
      (word & 0x0f0f0f0f0f0f0f0fULL) + 0x3434343434343434ULL;
  const uint64_t special_values =
      0x3e3e3e3e3e3e3e3eULL + ((word >> 2) & 0x0101010101010101ULL);
  const uint64_t sextets = (letter_values & letter_mask) |
                           (digit_values & digit_mask) |
                           (special_values & special_mask);

  const uint32_t a = (uint32_t)(sextets & 0xffu);
  const uint32_t b = (uint32_t)((sextets >> 8) & 0xffu);
  const uint32_t c = (uint32_t)((sextets >> 16) & 0xffu);
  const uint32_t d = (uint32_t)((sextets >> 24) & 0xffu);
  const uint32_t e = (uint32_t)((sextets >> 32) & 0xffu);
  const uint32_t f = (uint32_t)((sextets >> 40) & 0xffu);
  const uint32_t g = (uint32_t)((sextets >> 48) & 0xffu);
  const uint32_t h = (uint32_t)((sextets >> 56) & 0xffu);
  const uint32_t packed0 = (a << 18) | (b << 12) | (c << 6) | d;
  const uint32_t packed1 = (e << 18) | (f << 12) | (g << 6) | h;

  out[0] = (uint8_t)(packed0 >> 16);
  out[1] = (uint8_t)(packed0 >> 8);
  out[2] = (uint8_t)packed0;
  out[3] = (uint8_t)(packed1 >> 16);
  out[4] = (uint8_t)(packed1 >> 8);
  out[5] = (uint8_t)packed1;
  return 1;
}

static inline int base64_decode4_scalar(const uint8_t *src, int last_group,
                                        uint8_t *out, size_t *written) {
  uint8_t a, b, c, d;
  *written = 0;
  if (!base64_value(src[0], &a) || !base64_value(src[1], &b)) {
    return 0;
  }
  if (src[2] == '=') {
    if (!last_group || src[3] != '=') {
      return 0;
    }
    out[0] = (uint8_t)((a << 2) | (b >> 4));
    *written = 1;
    return 1;
  }
  if (!base64_value(src[2], &c)) {
    return 0;
  }
  if (src[3] == '=') {
    if (!last_group) {
      return 0;
    }
    out[0] = (uint8_t)((a << 2) | (b >> 4));
    out[1] = (uint8_t)((b << 4) | (c >> 2));
    *written = 2;
    return 1;
  }
  if (!base64_value(src[3], &d)) {
    return 0;
  }
  out[0] = (uint8_t)((a << 2) | (b >> 4));
  out[1] = (uint8_t)((b << 4) | (c >> 2));
  out[2] = (uint8_t)((c << 6) | d);
  *written = 3;
  return 1;
}

int scalar_base64_decode(const char *src, size_t srclen, char *out, size_t *outlen) {
  const uint8_t *input = (const uint8_t *)src;
  uint8_t *output = (uint8_t *)out;
  size_t in_pos = 0;
  size_t out_pos = 0;
  size_t fast_end = srclen;

  *outlen = 0;
  if ((srclen & 3u) != 0) {
    return 0;
  }
  if (srclen >= 4 && (input[srclen - 1] == '=' || input[srclen - 2] == '=')) {
    fast_end -= 4;
  }

  while (fast_end - in_pos >= 8) {
    uint64_t word;
    uint8_t decoded[6];
    memcpy(&word, input + in_pos, sizeof(word));
    if (!base64_decode8_swar(word, decoded)) {
      break;
    }
    memcpy(output + out_pos, decoded, sizeof(decoded));
    in_pos += 8;
    out_pos += 6;
  }

  while (in_pos < srclen) {
    size_t written = 0;
    if (!base64_decode4_scalar(input + in_pos, in_pos + 4 == srclen,
                               output + out_pos, &written)) {
      *outlen = out_pos;
      return 0;
    }
    in_pos += 4;
    out_pos += written;
  }
  *outlen = out_pos;
  return 1;
}

static inline char base64_encode_value(unsigned value) {
  if (value < 26) {
    return (char)('A' + value);
  }
  if (value < 52) {
    return (char)('a' + value - 26);
  }
  if (value < 62) {
    return (char)('0' + value - 52);
  }
  return value == 62 ? '+' : '/';
}

void scalar_base64_encode(const char *src, size_t srclen, char *out, size_t *outlen) {
  const uint8_t *input = (const uint8_t *)src;
  size_t in_pos = 0;
  size_t out_pos = 0;

  while (srclen - in_pos >= 3) {
    const uint8_t a = input[in_pos];
    const uint8_t b = input[in_pos + 1];
    const uint8_t c = input[in_pos + 2];
    out[out_pos++] = base64_encode_value(a >> 2);
    out[out_pos++] = base64_encode_value(((a & 3u) << 4) | (b >> 4));
    out[out_pos++] = base64_encode_value(((b & 15u) << 2) | (c >> 6));
    out[out_pos++] = base64_encode_value(c & 63u);
    in_pos += 3;
  }
  if (srclen - in_pos == 1) {
    const uint8_t a = input[in_pos];
    out[out_pos++] = base64_encode_value(a >> 2);
    out[out_pos++] = base64_encode_value((a & 3u) << 4);
    out[out_pos++] = '=';
    out[out_pos++] = '=';
  } else if (srclen - in_pos == 2) {
    const uint8_t a = input[in_pos];
    const uint8_t b = input[in_pos + 1];
    out[out_pos++] = base64_encode_value(a >> 2);
    out[out_pos++] = base64_encode_value(((a & 3u) << 4) | (b >> 4));
    out[out_pos++] = base64_encode_value((b & 15u) << 2);
    out[out_pos++] = '=';
  }
  *outlen = out_pos;
}

extern "C" void run(const void *input1, const void *input2, void *output,
                    int n, int parameter, int threads) {
  size_t len = 0;
  const int ok = scalar_base64_decode((const char *)input1, (size_t)n,
                                      ((char *)output) + 16, &len);
  *(uint64_t *)output = ok ? (uint64_t)len : UINT64_MAX;
}

#endif
