#include <stddef.h>
#include <stdint.h>
#include <string.h>

#if defined(__GNUC__) && (defined(__x86_64__) || defined(__i386__))
#include <immintrin.h>
#define BASE64_GCC_X86_SIMD 1
#else
#define BASE64_GCC_X86_SIMD 0
#endif

#ifndef SCALAR_B64
#define SCALAR_B64

/**
* Assumes recent x64 hardware with AVX2 instructions.
*/

#ifdef __cplusplus
extern "C" {
#endif /* __cplusplus */

int scalar_base64_decode(const char *src, size_t srclen, char *out, size_t *outlen);
void scalar_base64_encode(const char *src, size_t srclen, char *out, size_t *outlen);

#ifdef __cplusplus
}
#endif /* __cplusplus */

#endif

static const uint8_t base64_table_enc[] = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
                                   "abcdefghijklmnopqrstuvwxyz"
                                   "0123456789+/";

static const uint8_t base64_table_dec[] = {
    255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255,
    255, 255,
    255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255,
    255, 255,
    255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 62, 255, 255,
    255, 63,
    52, 53, 54, 55, 56, 57, 58, 59, 60, 61, 255, 255, 255, 254, 255, 255,
    255, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14,
    15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 255, 255, 255, 255, 255,
    255, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40,
    41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51, 255, 255, 255, 255, 255,
    255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255,
    255, 255,
    255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255,
    255, 255,
    255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255,
    255, 255,
    255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255,
    255, 255,
    255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255,
    255, 255,
    255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255,
    255, 255,
    255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255,
    255, 255,
    255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255,
    255, 255,
    255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255,
    255, 255,
    255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255,
    255, 255,
    255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255,
    255, 255,
    255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255,
    255, 255,
    255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255,
    255, 255,
    255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255,
    255, 255,
    255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255,
    255, 255,
    255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255,
    255, 255,
    255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255,
    255, 255,
    255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255,
    255, 255,
    255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255,
    255, 255,
    255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255,
    255, 255,
    255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255,
    255, 255,
    255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255,
    255, 255,
    255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255,
    255, 255,
    255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255,
    255, 255,
    255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255,
    255, 255,
    255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255,
    255, 255,
    255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255,
    255, 255,
    255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255,
    255, 255,
    255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255,
    255, 255,
    255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255,
    255, 255
};

struct base64_state {
  int eof;
  int bytes;
  unsigned char carry;
};

#define UNUSED(x) ((void)(x))
#define BASE64_ENC_STUB \
  UNUSED(state); UNUSED(src); UNUSED(srclen); UNUSED(out); *outlen = 0;
#define BASE64_DEC_STUB \
  UNUSED(state); UNUSED(src); UNUSED(srclen); UNUSED(out); UNUSED(outlen); return -1;

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
        uint64_t str = *(const uint64_t *)c;
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

#if BASE64_GCC_X86_SIMD
static __attribute__((target("avx2"))) int
base64_decode_block_avx2(const uint8_t *src, uint8_t *dst) {
  const __m256i chars = _mm256_loadu_si256((const __m256i *)src);
  const __m256i a = _mm256_set1_epi8('A');
  const __m256i z1 = _mm256_set1_epi8('Z' + 1);
  const __m256i lower_a = _mm256_set1_epi8('a');
  const __m256i lower_z1 = _mm256_set1_epi8('z' + 1);
  const __m256i zero = _mm256_set1_epi8('0');
  const __m256i nine1 = _mm256_set1_epi8('9' + 1);
  const __m256i upper = _mm256_and_si256(
      _mm256_cmpgt_epi8(chars, _mm256_set1_epi8('A' - 1)),
      _mm256_cmpgt_epi8(z1, chars));
  const __m256i lower = _mm256_and_si256(
      _mm256_cmpgt_epi8(chars, _mm256_set1_epi8('a' - 1)),
      _mm256_cmpgt_epi8(lower_z1, chars));
  const __m256i digits = _mm256_and_si256(
      _mm256_cmpgt_epi8(chars, _mm256_set1_epi8('0' - 1)),
      _mm256_cmpgt_epi8(nine1, chars));
  const __m256i plus = _mm256_cmpeq_epi8(chars, _mm256_set1_epi8('+'));
  const __m256i slash = _mm256_cmpeq_epi8(chars, _mm256_set1_epi8('/'));
  const __m256i valid = _mm256_or_si256(
      _mm256_or_si256(upper, lower),
      _mm256_or_si256(digits, _mm256_or_si256(plus, slash)));
  if (_mm256_movemask_epi8(valid) != -1) return 0;

  __m256i sextets = _mm256_or_si256(
      _mm256_and_si256(upper, _mm256_sub_epi8(chars, a)),
      _mm256_and_si256(lower,
          _mm256_add_epi8(_mm256_sub_epi8(chars, lower_a),
                          _mm256_set1_epi8(26))));
  sextets = _mm256_or_si256(sextets,
      _mm256_and_si256(digits,
          _mm256_add_epi8(_mm256_sub_epi8(chars, zero),
                          _mm256_set1_epi8(52))));
  sextets = _mm256_or_si256(sextets,
      _mm256_and_si256(plus, _mm256_set1_epi8(62)));
  sextets = _mm256_or_si256(sextets,
      _mm256_and_si256(slash, _mm256_set1_epi8(63)));

  alignas(32) uint8_t values[32];
  _mm256_store_si256((__m256i *)values, sextets);
  for (size_t i = 0; i < 32; i += 4) {
    *dst++ = (uint8_t)((values[i] << 2) | (values[i + 1] >> 4));
    *dst++ = (uint8_t)(((values[i + 1] & 0x0F) << 4) |
                       (values[i + 2] >> 2));
    *dst++ = (uint8_t)(((values[i + 2] & 0x03) << 6) | values[i + 3]);
  }
  return 1;
}

static __attribute__((target("avx512f,avx512bw"))) int
base64_decode_block_avx512(const uint8_t *src, uint8_t *dst) {
  const __m512i chars = _mm512_loadu_si512((const void *)src);
  const __mmask64 upper = _mm512_cmpgt_epi8_mask(
      chars, _mm512_set1_epi8('A' - 1));
  const __mmask64 upper_end = _mm512_cmpgt_epi8_mask(
      _mm512_set1_epi8('Z' + 1), chars);
  const __mmask64 lower = _mm512_cmpgt_epi8_mask(
      chars, _mm512_set1_epi8('a' - 1));
  const __mmask64 lower_end = _mm512_cmpgt_epi8_mask(
      _mm512_set1_epi8('z' + 1), chars);
  const __mmask64 digits = _mm512_cmpgt_epi8_mask(
      chars, _mm512_set1_epi8('0' - 1));
  const __mmask64 digits_end = _mm512_cmpgt_epi8_mask(
      _mm512_set1_epi8('9' + 1), chars);
  const __mmask64 upper_mask = upper & upper_end;
  const __mmask64 lower_mask = lower & lower_end;
  const __mmask64 digit_mask = digits & digits_end;
  const __mmask64 plus_mask = _mm512_cmpeq_epi8_mask(
      chars, _mm512_set1_epi8('+'));
  const __mmask64 slash_mask = _mm512_cmpeq_epi8_mask(
      chars, _mm512_set1_epi8('/'));
  const __mmask64 valid = upper_mask | lower_mask | digit_mask |
                          plus_mask | slash_mask;
  if (valid != ~(__mmask64)0) return 0;

  __m512i sextets = _mm512_or_si512(
      _mm512_and_si512(_mm512_movm_epi8(upper_mask),
          _mm512_sub_epi8(chars, _mm512_set1_epi8('A'))),
      _mm512_and_si512(_mm512_movm_epi8(lower_mask),
          _mm512_add_epi8(
              _mm512_sub_epi8(chars, _mm512_set1_epi8('a')),
              _mm512_set1_epi8(26))));
  sextets = _mm512_or_si512(sextets,
      _mm512_and_si512(_mm512_movm_epi8(digit_mask),
          _mm512_add_epi8(
              _mm512_sub_epi8(chars, _mm512_set1_epi8('0')),
              _mm512_set1_epi8(52))));
  sextets = _mm512_or_si512(sextets,
      _mm512_and_si512(_mm512_movm_epi8(plus_mask),
                       _mm512_set1_epi8(62)));
  sextets = _mm512_or_si512(sextets,
      _mm512_and_si512(_mm512_movm_epi8(slash_mask),
                       _mm512_set1_epi8(63)));

  alignas(64) uint8_t values[64];
  _mm512_store_si512((void *)values, sextets);
  for (size_t i = 0; i < 64; i += 4) {
    *dst++ = (uint8_t)((values[i] << 2) | (values[i + 1] >> 4));
    *dst++ = (uint8_t)(((values[i + 1] & 0x0F) << 4) |
                       (values[i + 2] >> 2));
    *dst++ = (uint8_t)(((values[i + 2] & 0x03) << 6) | values[i + 3]);
  }
  return 1;
}
#endif

static size_t base64_decode_simd_blocks(const uint8_t **src, uint8_t **out,
                                        size_t *srclen) {
  size_t outlen = 0;
#if BASE64_GCC_X86_SIMD
  if (*srclen < 32) return 0;
  if (__builtin_cpu_supports("avx512f") &&
      __builtin_cpu_supports("avx512bw")) {
    while (*srclen >= 64) {
      if (!base64_decode_block_avx512(*src, *out)) break;
      *src += 64;
      *out += 48;
      *srclen -= 64;
      outlen += 48;
    }
  }
  if (__builtin_cpu_supports("avx2")) {
    while (*srclen >= 32) {
      if (!base64_decode_block_avx2(*src, *out)) break;
      *src += 32;
      *out += 24;
      *srclen -= 32;
      outlen += 24;
    }
  }
#else
  (void)src;
  (void)out;
  (void)srclen;
#endif
  return outlen;
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

  if (st.bytes == 0) {
    outl += base64_decode_simd_blocks(&c, &o, &srclen);
  }

  switch (st.bytes) {
    for (;;) {
    case 0:
      while (srclen >= 13) {
        uint64_t str, res, dec;
        str = *(const uint64_t *)c;
        str = cpu_to_be64(str);
        if ((dec = base64_table_dec[str >> 56]) > 63) break;
        res = dec << 58;
        if ((dec = base64_table_dec[(str >> 48) & 0xFF]) > 63) break;
        res |= dec << 52;
        if ((dec = base64_table_dec[(str >> 40) & 0xFF]) > 63) break;
        res |= dec << 46;
        if ((dec = base64_table_dec[(str >> 32) & 0xFF]) > 63) break;
        res |= dec << 40;
        if ((dec = base64_table_dec[(str >> 24) & 0xFF]) > 63) break;
        res |= dec << 34;
        if ((dec = base64_table_dec[(str >> 16) & 0xFF]) > 63) break;
        res |= dec << 28;
        if ((dec = base64_table_dec[(str >> 8) & 0xFF]) > 63) break;
        res |= dec << 22;
        if ((dec = base64_table_dec[str & 0xFF]) > 63) break;
        res |= dec << 16;
        res = be64_to_cpu(res);
        *(uint64_t *)o = res;
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
