#ifndef SCALAR_B64
#define SCALAR_B64

/**
* Assumes recent x64 hardware with AVX2 instructions.
*/

#include <stddef.h>
#include <stdint.h>
#include <string.h>

#ifdef __cplusplus
extern "C" {
#endif /* __cplusplus */

/**
* We copy the code below from https://github.com/aklomp/base64
**/

/* Wrapper function to decode a plain string of given length. Output is written
 * to *out without trailing zero. Output length in bytes is written to *outlen.
 * The buffer in `out` has been allocated by the caller and is at least 3/4 the
 * size of the input. */
int scalar_base64_decode
	( const char		*src
	, size_t		 srclen
	, char			*out
	, size_t		*outlen
	) ;

/* Wrapper function to encode a plain string of given length. Output is written
 * to *out without trailing zero. Output length in bytes is written to *outlen.
 * The buffer in `out` has been allocated by the caller and is at least 4/3 the
 * size of the input.  */
void scalar_base64_encode
	( const char		*src
	, size_t		 srclen
	, char			*out
	, size_t		*outlen
	) ;

#ifdef __cplusplus
}
#endif /* __cplusplus */

#endif

/**
* We copy the code below from https://github.com/aklomp/base64
* We specialize it for 64-bit scalar processing.
**/

static const uint8_t base64_table_enc[] = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
                                   "abcdefghijklmnopqrstuvwxyz"
                                   "0123456789+/";

static inline uint8_t base64_decode_char(uint8_t c) {
  if (c >= 'A' && c <= 'Z') return (uint8_t)(c - 'A');
  if (c >= 'a' && c <= 'z') return (uint8_t)(c - 'a' + 26);
  if (c >= '0' && c <= '9') return (uint8_t)(c - '0' + 52);
  if (c == '+') return 62;
  if (c == '/') return 63;
  if (c == '=') return 254;
  return 255;
}

/* Expand each byte's top-bit predicate into an all-zero or all-one byte. */
static inline uint64_t base64_swar_expand_top64(uint64_t bits) {
  bits |= bits >> 1;
  bits |= bits >> 2;
  bits |= bits >> 4;
  return bits;
}

/* Convert exactly eight ASCII Base64 characters to eight packed sextets. */
static inline int base64_swar_decode8(const uint8_t *src, uint64_t *decoded) {
  uint64_t raw;
  memcpy(&raw, src, sizeof(raw));

  const uint64_t top = 0x8080808080808080ULL;
  const uint64_t ascii_mask = (~raw) & top;
  const uint64_t ascii = raw & 0x7f7f7f7f7f7f7f7fULL;
  const uint64_t folded = ascii & 0xdfdfdfdfdfdfdfdfULL;

  /* For 7-bit bytes, adding 128 - threshold sets the top bit at threshold. */
  const uint64_t letter_ge_a = (folded + 0x3f3f3f3f3f3f3f3fULL) & top;
  const uint64_t letter_ge_after_z = (folded + 0x2525252525252525ULL) & top;
  const uint64_t letters = letter_ge_a & ~letter_ge_after_z & ascii_mask;

  const uint64_t digit_ge_0 = (ascii + 0x5050505050505050ULL) & top;
  const uint64_t digit_ge_after_9 = (ascii + 0x4646464646464646ULL) & top;
  const uint64_t digits = digit_ge_0 & ~digit_ge_after_9 & ascii_mask;

  const uint64_t plus_diff = ascii ^ 0x2b2b2b2b2b2b2b2bULL;
  const uint64_t slash_diff = ascii ^ 0x2f2f2f2f2f2f2f2fULL;
  const uint64_t plus = ~(plus_diff + 0x7f7f7f7f7f7f7f7fULL) & top & ascii_mask;
  const uint64_t slash = ~(slash_diff + 0x7f7f7f7f7f7f7f7fULL) & top & ascii_mask;

  if ((letters | digits | plus | slash) != top) return 0;

  /* Keep every byte nonzero before subtracting one, preventing lane borrows. */
  const uint64_t letter_values =
      (((folded & 0x1f1f1f1f1f1f1f1fULL) | 0x2020202020202020ULL) -
       0x0101010101010101ULL) & 0x1f1f1f1f1f1f1f1fULL;
  const uint64_t digit_values = ascii + 0x0404040404040404ULL;

  const uint64_t letter_mask = base64_swar_expand_top64(letters);
  const uint64_t digit_mask = base64_swar_expand_top64(digits);
  const uint64_t plus_mask = base64_swar_expand_top64(plus);
  const uint64_t slash_mask = base64_swar_expand_top64(slash);
  *decoded = (letter_values & letter_mask) |
             (digit_values & digit_mask) |
             (0x3e3e3e3e3e3e3e3eULL & plus_mask) |
             (0x3f3f3f3f3f3f3f3fULL & slash_mask);
  return 1;
}

/* Emit exactly six bytes from eight sextets, in input order on either endian. */
static inline void base64_swar_emit8(uint64_t sextets, uint8_t *out) {
  uint8_t q[8];
  memcpy(q, &sextets, sizeof(q));
  out[0] = (uint8_t)((q[0] << 2) | (q[1] >> 4));
  out[1] = (uint8_t)((q[1] << 4) | (q[2] >> 2));
  out[2] = (uint8_t)((q[2] << 6) | q[3]);
  out[3] = (uint8_t)((q[4] << 2) | (q[5] >> 4));
  out[4] = (uint8_t)((q[5] << 4) | (q[6] >> 2));
  out[5] = (uint8_t)((q[6] << 6) | q[7]);
}

struct base64_state {
  int eof;
  int bytes;
  unsigned char carry;
};

#define UNUSED(x) ((void)(x))
#define BASE64_ENC_STUB UNUSED(state); UNUSED(src); UNUSED(srclen); UNUSED(out); *outlen = 0;
#define BASE64_DEC_STUB UNUSED(state); UNUSED(src); UNUSED(srclen); UNUSED(out); UNUSED(outlen); return -1;

struct codec {
  void (*enc)(struct base64_state *state, const char *src, size_t srclen,
              char *out, size_t *outlen);
  int (*dec)(struct base64_state *state, const char *src, size_t srclen,
             char *out, size_t *outlen);
};

#if (__BYTE_ORDER__ == __ORDER_LITTLE_ENDIAN__)
#define BASE64_LITTLE_ENDIAN 1
#else
#define BASE64_LITTLE_ENDIAN 0
#endif

#ifdef __LITTLE_ENDIAN__
#define BASE64_LITTLE_ENDIAN 1
#endif

#ifdef __BIG_ENDIAN__
#define BASE64_LITTLE_ENDIAN 0
#endif

#if BASE64_LITTLE_ENDIAN
#if defined(_MSC_VER)
#define cpu_to_be32(x) _byteswap_ulong(x)
#define cpu_to_be64(x) _byteswap_uint64(x)
#define be32_to_cpu(x) _byteswap_ulong(x)
#define be64_to_cpu(x) _byteswap_uint64(x)
#else
#define cpu_to_be32(x) __builtin_bswap32(x)
#define cpu_to_be64(x) __builtin_bswap64(x)
#define be32_to_cpu(x) __builtin_bswap32(x)
#define be64_to_cpu(x) __builtin_bswap64(x)
#endif
#else
#define cpu_to_be32(x) (x)
#define cpu_to_be64(x) (x)
#define be32_to_cpu(x) (x)
#define be64_to_cpu(x) (x)
#endif

#ifdef _INTEGRAL_MAX_BITS
#define BASE64_WORDSIZE _INTEGRAL_MAX_BITS
#else
#define BASE64_WORDSIZE __WORDSIZE
#endif

#define BASE64_AEOF 1
#define BASE64_EOF 2

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
        uint64_t str = *(uint64_t *)c;
        str = cpu_to_be64(str);
        *o++ = base64_table_enc[(str >> 58) & 0x3F];
        *o++ = base64_table_enc[(str >> 52) & 0x3F];
        *o++ = base64_table_enc[(str >> 46) & 0x3F];
        *o++ = base64_table_enc[(str >> 40) & 0x3F];
        *o++ = base64_table_enc[(str >> 34) & 0x3F];
        *o++ = base64_table_enc[(str >> 28) & 0x3F];
        *o++ = base64_table_enc[(str >> 22) & 0x3F];
        *o++ = base64_table_enc[(str >> 16) & 0x3F];
        c += 6;
        outl += 8;
        srclen -= 6;
      }

      if (srclen-- == 0) break;
      *o++ = base64_table_enc[*c >> 2];
      st.carry = (*c++ << 4) & 0x30;
      st.bytes++;
      outl += 1;

    case 1:
      if (srclen-- == 0) break;
      *o++ = base64_table_enc[st.carry | (*c >> 4)];
      st.carry = (*c++ << 2) & 0x3C;
      st.bytes++;
      outl += 1;

    case 2:
      if (srclen-- == 0) break;
      *o++ = base64_table_enc[st.carry | (*c >> 6)];
      *o++ = base64_table_enc[*c++ & 0x3F];
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
      ret = ((base64_decode_char(*c++) == 254) && (srclen == 1)) ? 1 : 0;
    }
    return ret;
  }

  switch (st.bytes) {
    for (;;) {
    case 0:
      /* Retain at least one final four-character group for the scalar path. */
      while (srclen >= 12) {
        uint64_t decoded;
        if (!base64_swar_decode8(c, &decoded)) break;
        base64_swar_emit8(decoded, o);
        c += 8;
        o += 6;
        outl += 6;
        srclen -= 8;
      }

      if (srclen-- == 0) {
        ret = 1;
        break;
      }
      if ((q = base64_decode_char(*c++)) >= 254) {
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
      if ((q = base64_decode_char(*c++)) >= 254) {
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
      if ((q = base64_decode_char(*c++)) >= 254) {
        st.bytes++;
        if (q == 254) {
          if (srclen-- != 0) {
            st.bytes = 0;
            st.eof = BASE64_EOF;
            q = base64_decode_char(*c++);
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
      if ((q = base64_decode_char(*c++)) >= 254) {
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

void scalar_base64_encode(const char *src, size_t srclen, char *out,
                          size_t *outlen) {
  size_t s;
  size_t t;
  struct base64_state state;
  base64_stream_encode_init(&state);
  base64_stream_encode(&state, src, srclen, out, &s);
  base64_stream_encode_final(&state, out + s, &t);
  *outlen = s + t;
}

int scalar_base64_decode(const char *src, size_t srclen, char *out,
                         size_t *outlen) {
  int ret;
  struct base64_state state;
  base64_stream_decode_init(&state);
  ret = base64_stream_decode(&state, src, srclen, out, outlen);
  if (ret && (state.bytes == 0)) return ret;
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
  int ok = scalar_base64_decode((const char *)input1, n,
                                ((char *)output) + 16, &len);
  *(uint64_t *)output = ok ? len : UINT64_MAX;
}
