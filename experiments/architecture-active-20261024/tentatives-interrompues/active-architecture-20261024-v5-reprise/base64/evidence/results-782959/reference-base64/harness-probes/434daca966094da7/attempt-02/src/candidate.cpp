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
#endif

static const uint8_t base64_table_enc[] = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
                                           "abcdefghijklmnopqrstuvwxyz"
                                           "0123456789+/";

static const uint8_t base64_table_dec[] = {
    255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255,
    255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255,
    255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 62, 255, 255, 255, 63,
    52, 53, 54, 55, 56, 57, 58, 59, 60, 61, 255, 255, 255, 254, 255, 255,
    255, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14,
    15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 255, 255, 255, 255, 255,
    255, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40,
    41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51, 255, 255, 255, 255, 255,
    255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255,
    255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255,
    255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255,
    255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255,
    255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255,
    255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255,
    255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255,
    255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255
};

struct base64_state {
  int eof;
  int bytes;
  unsigned char carry;
};

#if (__BYTE_ORDER__ == __ORDER_LITTLE_ENDIAN__)
#define BASE64_LITTLE_ENDIAN 1
#else
#define BASE64_LITTLE_ENDIAN 0
#endif

#ifdef __LITTLE_ENDIAN__
#undef BASE64_LITTLE_ENDIAN
#define BASE64_LITTLE_ENDIAN 1
#endif

#ifdef __BIG_ENDIAN__
#undef BASE64_LITTLE_ENDIAN
#define BASE64_LITTLE_ENDIAN 0
#endif

#if BASE64_LITTLE_ENDIAN
#if defined(_MSC_VER)
#define cpu_to_be64(x) _byteswap_uint64(x)
#else
#define cpu_to_be64(x) __builtin_bswap64(x)
#endif
#else
#define cpu_to_be64(x) (x)
#endif

#define BASE64_AEOF 1
#define BASE64_EOF 2

static inline uint64_t b64_repeat8(uint32_t value) {
  return (uint64_t)(value & 0xffu) * 0x0101010101010101ULL;
}

static inline uint64_t b64_ge8(uint64_t value, uint32_t bound) {
  const uint64_t high = 0x8080808080808080ULL;
  return ((value | high) - b64_repeat8(bound)) & high;
}

static inline uint64_t b64_le8(uint64_t value, uint32_t bound) {
  const uint64_t high = 0x8080808080808080ULL;
  return ((b64_repeat8(bound) | high) - value) & high;
}

static inline uint64_t b64_range8(uint64_t value, uint32_t low, uint32_t high) {
  return b64_ge8(value, low) & b64_le8(value, high);
}

static inline uint64_t b64_expand_lane_flags(uint64_t flags) {
  return (flags >> 7) * 0xffULL;
}

static inline int b64_decode8_word(uint64_t word, uint64_t *decoded) {
  const uint64_t lane_high = 0x8080808080808080ULL;
  if ((word & lane_high) != 0) {
    return 0;
  }

  const uint64_t upper = b64_range8(word, 'A', 'Z');
  const uint64_t lower = b64_range8(word, 'a', 'z');
  const uint64_t digit = b64_range8(word, '0', '9');
  const uint64_t plus = b64_range8(word, '+', '+');
  const uint64_t slash = b64_range8(word, '/', '/');
  const uint64_t valid = upper | lower | digit | plus | slash;
  if (valid != lane_high) {
    return 0;
  }

  const uint64_t upper_bytes = b64_expand_lane_flags(upper);
  const uint64_t lower_bytes = b64_expand_lane_flags(lower);
  const uint64_t digit_bytes = b64_expand_lane_flags(digit);
  const uint64_t plus_bytes = b64_expand_lane_flags(plus);
  const uint64_t slash_bytes = b64_expand_lane_flags(slash);
  const uint64_t sextets =
      ((word & upper_bytes) & ~0ULL) - (b64_repeat8('A') & upper_bytes) |
      ((word & lower_bytes) - (b64_repeat8('a' - 26) & lower_bytes)) |
      ((word & digit_bytes) + (b64_repeat8(4) & digit_bytes)) |
      (b64_repeat8(62) & plus_bytes) |
      (b64_repeat8(63) & slash_bytes);

  const uint32_t s0 = (uint32_t)(sextets & 0x3fu);
  const uint32_t s1 = (uint32_t)((sextets >> 8) & 0x3fu);
  const uint32_t s2 = (uint32_t)((sextets >> 16) & 0x3fu);
  const uint32_t s3 = (uint32_t)((sextets >> 24) & 0x3fu);
  const uint32_t s4 = (uint32_t)((sextets >> 32) & 0x3fu);
  const uint32_t s5 = (uint32_t)((sextets >> 40) & 0x3fu);
  const uint32_t s6 = (uint32_t)((sextets >> 48) & 0x3fu);
  const uint32_t s7 = (uint32_t)((sextets >> 56) & 0x3fu);
  const uint8_t b0 = (uint8_t)((s0 << 2) | (s1 >> 4));
  const uint8_t b1 = (uint8_t)(((s1 & 0x0fu) << 4) | (s2 >> 2));
  const uint8_t b2 = (uint8_t)(((s2 & 0x03u) << 6) | s3);
  const uint8_t b3 = (uint8_t)((s4 << 2) | (s5 >> 4));
  const uint8_t b4 = (uint8_t)(((s5 & 0x0fu) << 4) | (s6 >> 2));
  const uint8_t b5 = (uint8_t)(((s6 & 0x03u) << 6) | s7);
  *decoded = (uint64_t)b0 | ((uint64_t)b1 << 8) | ((uint64_t)b2 << 16) |
             ((uint64_t)b3 << 24) | ((uint64_t)b4 << 32) | ((uint64_t)b5 << 40);
  return 1;
}

void base64_stream_encode_scalar(struct base64_state *state, const char *src,
                                 size_t srclen, char *out, size_t *outlen) {
  const uint8_t *c = (const uint8_t *)src;
  uint8_t *o = (uint8_t *)out;
  size_t outl = 0;
  struct base64_state st;
  st.bytes = state->bytes;
  st.carry = state->carry;

  switch (st.bytes) {
    for (;;) {
    case 0:
      while (srclen >= 8) {
        uint64_t str = *(const uint64_t *)c;
        str = cpu_to_be64(str);
        *o++ = base64_table_enc[(str >> 58) & 0x3f];
        *o++ = base64_table_enc[(str >> 52) & 0x3f];
        *o++ = base64_table_enc[(str >> 46) & 0x3f];
        *o++ = base64_table_enc[(str >> 40) & 0x3f];
        *o++ = base64_table_enc[(str >> 34) & 0x3f];
        *o++ = base64_table_enc[(str >> 28) & 0x3f];
        *o++ = base64_table_enc[(str >> 22) & 0x3f];
        *o++ = base64_table_enc[(str >> 16) & 0x3f];
        c += 6;
        outl += 8;
        srclen -= 6;
      }
      if (srclen-- == 0) {
        break;
      }
      *o++ = base64_table_enc[*c >> 2];
      st.carry = (*c++ << 4) & 0x30;
      st.bytes++;
      outl++;

    case 1:
      if (srclen-- == 0) {
        break;
      }
      *o++ = base64_table_enc[st.carry | (*c >> 4)];
      st.carry = (*c++ << 2) & 0x3c;
      st.bytes++;
      outl++;

    case 2:
      if (srclen-- == 0) {
        break;
      }
      *o++ = base64_table_enc[st.carry | (*c >> 6)];
      *o++ = base64_table_enc[*c++ & 0x3f];
      st.bytes = 0;
      outl += 2;
    }
  }
  state->bytes = st.bytes;
  state->carry = st.carry;
  *outlen = outl;
}

int base64_stream_decode_scalar(struct base64_state *state, const char *src,
                                size_t srclen, char *out, size_t *outlen) {
  int ret = 0;
  const uint8_t *c = (const uint8_t *)src;
  uint8_t *o = (uint8_t *)out;
  uint8_t q;
  size_t outl = 0;
  struct base64_state st;
  st.eof = state->eof;
  st.bytes = state->bytes;
  st.carry = state->carry;

  if (st.eof) {
    *outlen = 0;
    ret = 0;
    if (srclen && (st.eof == BASE64_AEOF)) {
      state->bytes = 0;
      state->eof = BASE64_EOF;
      ret = ((base64_table_dec[*c++] == 254) && (srclen == 1)) ? 1 : 0;
    }
    return ret;
  }

  switch (st.bytes) {
    for (;;) {
    case 0:
      while (srclen >= 8) {
        uint64_t word;
        uint64_t decoded;
        memcpy(&word, c, sizeof(word));
#if BASE64_LITTLE_ENDIAN
        /* The machine word already has the first input byte in its low lane. */
#else
        word = __builtin_bswap64(word);
#endif
        if (!b64_decode8_word(word, &decoded)) {
          break;
        }
        o[0] = (uint8_t)decoded;
        o[1] = (uint8_t)(decoded >> 8);
        o[2] = (uint8_t)(decoded >> 16);
        o[3] = (uint8_t)(decoded >> 24);
        o[4] = (uint8_t)(decoded >> 32);
        o[5] = (uint8_t)(decoded >> 40);
        c += 8;
        o += 6;
        outl += 6;
        srclen -= 8;
      }
      if (srclen-- == 0) {
        ret = 1;
        break;
      }
      if ((q = base64_table_dec[*c++]) >= 254) {
        st.eof = BASE64_EOF;
        break;
      }
      st.carry = q << 2;
      st.bytes++;

    case 1:
      if (srclen-- == 0) {
        ret = 1;
        break;
      }
      if ((q = base64_table_dec[*c++]) >= 254) {
        st.eof = BASE64_EOF;
        break;
      }
      *o++ = st.carry | (q >> 4);
      st.carry = q << 4;
      st.bytes++;
      outl++;

    case 2:
      if (srclen-- == 0) {
        ret = 1;
        break;
      }
      if ((q = base64_table_dec[*c++]) >= 254) {
        st.bytes++;
        if (q == 254) {
          if (srclen-- != 0) {
            st.bytes = 0;
            st.eof = BASE64_EOF;
            q = base64_table_dec[*c++];
            ret = ((q == 254) && (srclen == 0)) ? 1 : 0;
            break;
          } else {
            st.eof = BASE64_AEOF;
            ret = 1;
            break;
          }
        }
        break;
      }
      *o++ = st.carry | (q >> 2);
      st.carry = q << 6;
      st.bytes++;
      outl++;

    case 3:
      if (srclen-- == 0) {
        ret = 1;
        break;
      }
      if ((q = base64_table_dec[*c++]) >= 254) {
        st.bytes = 0;
        st.eof = BASE64_EOF;
        ret = ((q == 254) && (srclen == 0)) ? 1 : 0;
        break;
      }
      *o++ = st.carry | q;
      st.carry = 0;
      st.bytes = 0;
      outl++;
    }
  }
  state->eof = st.eof;
  state->bytes = st.bytes;
  state->carry = st.carry;
  *outlen = outl;
  return ret;
}

static void base64_stream_encode_init(struct base64_state *state) {
  state->eof = 0;
  state->bytes = 0;
  state->carry = 0;
}

static void base64_stream_encode(struct base64_state *state, const char *src,
                                 size_t srclen, char *out, size_t *outlen) {
  base64_stream_encode_scalar(state, src, srclen, out, outlen);
}

static void base64_stream_encode_final(struct base64_state *state, char *out,
                                       size_t *outlen) {
  uint8_t *o = (uint8_t *)out;
  if (state->bytes == 1) {
    *o++ = base64_table_enc[state->carry];
    *o++ = '=';
    *o++ = '=';
    *outlen = 3;
    return;
  }
  if (state->bytes == 2) {
    *o++ = base64_table_enc[state->carry];
    *o++ = '=';
    *outlen = 2;
    return;
  }
  *outlen = 0;
}

static void base64_stream_decode_init(struct base64_state *state) {
  state->eof = 0;
  state->bytes = 0;
  state->carry = 0;
}

static int base64_stream_decode(struct base64_state *state, const char *src,
                                size_t srclen, char *out, size_t *outlen) {
  return base64_stream_decode_scalar(state, src, srclen, out, outlen);
}

void scalar_base64_encode(const char *src, size_t srclen, char *out, size_t *outlen) {
  size_t s;
  size_t t;
  struct base64_state state;
  base64_stream_encode_init(&state);
  base64_stream_encode(&state, src, srclen, out, &s);
  base64_stream_encode_final(&state, out + s, &t);
  *outlen = s + t;
}

int scalar_base64_decode(const char *src, size_t srclen, char *out, size_t *outlen) {
  int ret;
  struct base64_state state;
  base64_stream_decode_init(&state);
  ret = base64_stream_decode(&state, src, srclen, out, outlen);
  if (ret && (state.bytes == 0)) {
    return ret;
  }
  return 0;
}

#include <cstdint>
#include <cstring>
#include <cmath>
#include <algorithm>
#include <omp.h>

extern "C" void run(const void *input1, const void *input2, void *output,
                    int n, int parameter, int threads) {
  size_t len = 0;
  int ok = scalar_base64_decode((const char *)input1, (size_t)n,
                                ((char *)output) + 16, &len);
  *(uint64_t *)output = ok ? len : UINT64_MAX;
}
