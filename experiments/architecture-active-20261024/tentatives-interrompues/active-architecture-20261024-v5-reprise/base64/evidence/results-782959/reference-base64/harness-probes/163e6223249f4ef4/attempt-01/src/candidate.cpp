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

static inline uint64_t base64_expand_lane_mask(uint64_t flags) {
  return flags | (flags - (flags >> 15));
}

static inline int base64_decode4_swar(uint32_t word, uint8_t *out) {
  const uint64_t lane_bias = 0x8000800080008000ULL;
  const uint64_t lane_ones = 0x0001000100010001ULL;
  const uint64_t low5_mask = 0x001f001f001f001fULL;
  const uint64_t low4_mask = 0x000f000f000f000fULL;
  const uint64_t bit2_mask = 0x0004000400040004ULL;
  const uint64_t bit5_mask = 0x0020002000200020ULL;
  const uint64_t bit6_mask = 0x0040004000400040ULL;
  const uint64_t bit7_mask = 0x0080008000800080ULL;
  const uint64_t lanes =
      (uint64_t)(word & 0xffu) |
      ((uint64_t)((word >> 8) & 0xffu) << 16) |
      ((uint64_t)((word >> 16) & 0xffu) << 32) |
      ((uint64_t)((word >> 24) & 0xffu) << 48);
  const uint64_t compared = lanes | lane_bias;
  const uint64_t low5 = lanes & low5_mask;
  const uint64_t low_compared = low5 | lane_bias;
  const uint64_t letter_shape =
      ((lanes & bit6_mask) << 1) & ~lanes & bit7_mask;
  const uint64_t ge_low_1 = (low_compared - lane_ones) & lane_bias;
  const uint64_t ge_low_27 =
      (low_compared - 0x001b001b001b001bULL) & lane_bias;
  const uint64_t letters = letter_shape & ge_low_1 & ~ge_low_27;
  const uint64_t ge_zero =
      (compared - 0x0030003000300030ULL) & lane_bias;
  const uint64_t ge_after_nine =
      (compared - 0x003a003a003a003aULL) & lane_bias;
  const uint64_t digits = ge_zero & ~ge_after_nine;
  const uint64_t special_diff =
      (lanes ^ 0x002b002b002b002bULL) & 0x00fb00fb00fb00fbULL;
  const uint64_t specials =
      ~((special_diff | lane_bias) - lane_ones) & lane_bias;
  const uint64_t valid = letters | digits | specials;

  if (valid != lane_bias) {
    return 0;
  }

  const uint64_t letter_mask = base64_expand_lane_mask(letters);
  const uint64_t digit_mask = base64_expand_lane_mask(digits);
  const uint64_t special_mask = base64_expand_lane_mask(specials);
  const uint64_t lowercase = (lanes & bit5_mask) >> 5;
  const uint64_t lower_offset =
      (lowercase << 1) + (lowercase << 3) + (lowercase << 4);
  const uint64_t letter_values =
      ((low5 + 0x001f001f001f001fULL) & low5_mask) + lower_offset;
  const uint64_t digit_values = (lanes & low4_mask) + 0x0034003400340034ULL;
  const uint64_t special_values =
      0x003e003e003e003eULL + ((lanes & bit2_mask) >> 2);
  const uint64_t sextets =
      (letter_values & letter_mask) |
      (digit_values & digit_mask) |
      (special_values & special_mask);
  const uint32_t a = (uint32_t)(sextets & 0xffu);
  const uint32_t b = (uint32_t)((sextets >> 16) & 0xffu);
  const uint32_t c = (uint32_t)((sextets >> 32) & 0xffu);
  const uint32_t d = (uint32_t)((sextets >> 48) & 0xffu);
  const uint32_t packed = (a << 18) | (b << 12) | (c << 6) | d;

  out[0] = (uint8_t)(packed >> 16);
  out[1] = (uint8_t)(packed >> 8);
  out[2] = (uint8_t)packed;
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
    uint32_t words[2];
    uint8_t decoded[6];
    memcpy(words, input + in_pos, sizeof(words));
    if (!base64_decode4_swar(words[0], decoded) ||
        !base64_decode4_swar(words[1], decoded + 3)) {
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
