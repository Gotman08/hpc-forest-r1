#ifndef SCALAR_B64
#define SCALAR_B64
#include <stddef.h>
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif
int scalar_base64_decode(const char *src, size_t srclen, char *out, size_t *outlen);
void scalar_base64_encode(const char *src, size_t srclen, char *out, size_t *outlen);
#ifdef __cplusplus
}
#endif
#endif

#include <cstdint>
#include <cstring>
#include <cmath>
#include <algorithm>
#include <omp.h>
#if defined(__GNUC__) && (defined(__x86_64__) || defined(__i386__))
#define BASE64_X86_SIMD 1
#include <immintrin.h>
#else
#define BASE64_X86_SIMD 0
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
    255, 255
};

struct base64_state {
  int eof;
  int bytes;
  unsigned char carry;
};
#define UNUSED(x) ((void)(x))
#define BASE64_ENC_STUB UNUSED(state); UNUSED(src); UNUSED(srclen); UNUSED(out); *outlen = 0;
#define BASE64_DEC_STUB UNUSED(state); UNUSED(src); UNUSED(srclen); UNUSED(out); UNUSED(outlen); return -1;
struct codec {
  void (*enc)(struct base64_state *, const char *, size_t, char *, size_t *);
  int (*dec)(struct base64_state *, const char *, size_t, char *, size_t *);
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
      outl++;
    case 1:
      if (srclen-- == 0) break;
      *o++ = base64_table_enc[st.carry | (*c >> 4)];
      st.carry = (*c++ << 2) & 0x3C;
      st.bytes++;
      outl++;
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

#if BASE64_X86_SIMD
alignas(64) static const uint8_t base64_pack_control[64] = {
    2, 1, 0, 6, 5, 4, 10, 9, 8, 14, 13, 12, 255, 255, 255, 255,
    2, 1, 0, 6, 5, 4, 10, 9, 8, 14, 13, 12, 255, 255, 255, 255,
    2, 1, 0, 6, 5, 4, 10, 9, 8, 14, 13, 12, 255, 255, 255, 255,
    2, 1, 0, 6, 5, 4, 10, 9, 8, 14, 13, 12, 255, 255, 255, 255
};
// AVX2 maps ordinary symbols with a correction selected by the high nibble.
// The low-nibble table supplies the two special corrections for '+' and '/'.
alignas(32) static const int8_t base64_avx2_high_correction[32] = {
    0, 0, 0, 4, -65, -65, -71, -71, 0, 0, 0, 0, 0, 0, 0, 0,
    0, 0, 0, 4, -65, -65, -71, -71, 0, 0, 0, 0, 0, 0, 0, 0
};
alignas(32) static const int8_t base64_avx2_low_correction[32] = {
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 19, 0, 0, 0, 16,
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 19, 0, 0, 0, 16
};
#endif

#if BASE64_X86_SIMD
static __attribute__((target("avx2"))) size_t
base64_decode_avx2_blocks(const uint8_t *src, size_t srclen, uint8_t *out,
                          size_t *out_count) {
  size_t consumed = 0, produced = 0;
  while (srclen >= 32) {
    const __m256i x = _mm256_loadu_si256((const __m256i *)src);
    const __m256i upper = _mm256_and_si256(
        _mm256_cmpgt_epi8(x, _mm256_set1_epi8('A' - 1)),
        _mm256_cmpgt_epi8(_mm256_set1_epi8('Z' + 1), x));
    const __m256i lower = _mm256_and_si256(
        _mm256_cmpgt_epi8(x, _mm256_set1_epi8('a' - 1)),
        _mm256_cmpgt_epi8(_mm256_set1_epi8('z' + 1), x));
    const __m256i digits = _mm256_and_si256(
        _mm256_cmpgt_epi8(x, _mm256_set1_epi8('0' - 1)),
        _mm256_cmpgt_epi8(_mm256_set1_epi8('9' + 1), x));
    const __m256i plus = _mm256_cmpeq_epi8(x, _mm256_set1_epi8('+'));
    const __m256i slash = _mm256_cmpeq_epi8(x, _mm256_set1_epi8('/'));
    const __m256i valid = _mm256_or_si256(
        _mm256_or_si256(upper, lower),
        _mm256_or_si256(digits, _mm256_or_si256(plus, slash)));
    if (_mm256_movemask_epi8(valid) != -1) break;

    const __m256i high_nibble = _mm256_and_si256(
        _mm256_srli_epi16(x, 4), _mm256_set1_epi8(0x0f));
    const __m256i low_nibble = _mm256_and_si256(x, _mm256_set1_epi8(0x0f));
    const __m256i high_correction = _mm256_shuffle_epi8(
        _mm256_load_si256((const __m256i *)base64_avx2_high_correction),
        high_nibble);
    const __m256i special_mask = _mm256_or_si256(plus, slash);
    const __m256i low_correction = _mm256_and_si256(
        special_mask,
        _mm256_shuffle_epi8(
            _mm256_load_si256((const __m256i *)base64_avx2_low_correction),
            low_nibble));
    const __m256i values = _mm256_add_epi8(
        _mm256_add_epi8(x, high_correction), low_correction);
    const __m256i pairs = _mm256_maddubs_epi16(
        values, _mm256_set1_epi16(0x0140));
    const __m256i words = _mm256_madd_epi16(
        pairs, _mm256_set1_epi32(0x00011000));
    const __m256i packed = _mm256_shuffle_epi8(
        words, _mm256_load_si256((const __m256i *)base64_pack_control));
    alignas(32) uint8_t packed_bytes[32];
    _mm256_store_si256((__m256i *)packed_bytes, packed);
    memcpy(out + produced, packed_bytes, 12);
    memcpy(out + produced + 12, packed_bytes + 16, 12);
    produced += 24;
    src += 32;
    srclen -= 32;
    consumed += 32;
  }
  *out_count = produced;
  return consumed;
}

static __attribute__((target("avx512f,avx512bw"))) size_t
base64_decode_avx512_blocks(const uint8_t *src, size_t srclen, uint8_t *out,
                            size_t *out_count) {
  size_t consumed = 0, produced = 0;
  while (srclen >= 64) {
    const __m512i x = _mm512_loadu_si512((const void *)src);
    const __mmask64 upper = _mm512_cmpgt_epi8_mask(x, _mm512_set1_epi8('A' - 1)) &
        _mm512_cmpgt_epi8_mask(_mm512_set1_epi8('Z' + 1), x);
    const __mmask64 lower = _mm512_cmpgt_epi8_mask(x, _mm512_set1_epi8('a' - 1)) &
        _mm512_cmpgt_epi8_mask(_mm512_set1_epi8('z' + 1), x);
    const __mmask64 digits = _mm512_cmpgt_epi8_mask(x, _mm512_set1_epi8('0' - 1)) &
        _mm512_cmpgt_epi8_mask(_mm512_set1_epi8('9' + 1), x);
    const __mmask64 plus = _mm512_cmpeq_epi8_mask(x, _mm512_set1_epi8('+'));
    const __mmask64 slash = _mm512_cmpeq_epi8_mask(x, _mm512_set1_epi8('/'));
    const __mmask64 valid = upper | lower | digits | plus | slash;
    if (valid != (__mmask64)-1) break;
    __m512i values = _mm512_maskz_mov_epi8(
        upper, _mm512_sub_epi8(x, _mm512_set1_epi8('A')));
    values = _mm512_or_si512(values, _mm512_maskz_mov_epi8(
        lower, _mm512_sub_epi8(x, _mm512_set1_epi8('a' - 26))));
    values = _mm512_or_si512(values, _mm512_maskz_mov_epi8(
        digits, _mm512_add_epi8(x, _mm512_set1_epi8(4))));
    values = _mm512_or_si512(values, _mm512_maskz_mov_epi8(
        plus, _mm512_set1_epi8(62)));
    values = _mm512_or_si512(values, _mm512_maskz_mov_epi8(
        slash, _mm512_set1_epi8(63)));
    const __m512i pairs = _mm512_maddubs_epi16(
        values, _mm512_set1_epi16(0x0140));
    const __m512i words = _mm512_madd_epi16(
        pairs, _mm512_set1_epi32(0x00011000));
    const __m512i packed = _mm512_shuffle_epi8(
        words, _mm512_load_si512((const void *)base64_pack_control));
    alignas(64) uint8_t packed_bytes[64];
    _mm512_store_si512((void *)packed_bytes, packed);
    memcpy(out + produced, packed_bytes, 12);
    memcpy(out + produced + 12, packed_bytes + 16, 12);
    memcpy(out + produced + 24, packed_bytes + 32, 12);
    memcpy(out + produced + 36, packed_bytes + 48, 12);
    produced += 48;
    src += 64;
    srclen -= 64;
    consumed += 64;
  }
  *out_count = produced;
  return consumed;
}
#endif

static size_t base64_decode_simd_blocks(const uint8_t *src, size_t srclen,
                                        uint8_t *out, size_t *out_count) {
  size_t consumed = 0, produced = 0;
#if BASE64_X86_SIMD
  __builtin_cpu_init();
  if (srclen >= 64 && __builtin_cpu_supports("avx512f") &&
      __builtin_cpu_supports("avx512bw")) {
    size_t nout = 0;
    size_t n = base64_decode_avx512_blocks(src, srclen, out, &nout);
    src += n;
    srclen -= n;
    out += nout;
    consumed += n;
    produced += nout;
  }
  if (srclen >= 32 && __builtin_cpu_supports("avx2")) {
    size_t nout = 0;
    size_t n = base64_decode_avx2_blocks(src, srclen, out, &nout);
    consumed += n;
    produced += nout;
  }
#endif
  *out_count = produced;
  return consumed;
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
  if (st.bytes == 0 && srclen >= 32) {
    size_t simd_out = 0;
    size_t consumed = base64_decode_simd_blocks(c, srclen, o, &simd_out);
    c += consumed;
    o += simd_out;
    srclen -= consumed;
    outl += simd_out;
  }
  switch (st.bytes) {
    for (;;) {
    case 0:
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
extern "C" void scalar_base64_encode(const char *src, size_t srclen,
                                     char *out, size_t *outlen) {
  size_t s, t;
  struct base64_state state;
  base64_stream_encode_init(&state);
  base64_stream_encode(&state, src, srclen, out, &s);
  base64_stream_encode_final(&state, out + s, &t);
  *outlen = s + t;
}
extern "C" int scalar_base64_decode(const char *src, size_t srclen,
                                    char *out, size_t *outlen) {
  int ret;
  struct base64_state state;
  base64_stream_decode_init(&state);
  ret = base64_stream_decode(&state, src, srclen, out, outlen);
  if (ret && (state.bytes == 0)) return ret;
  return 0;
}
extern "C" void run(const void *input1, const void *input2, void *output,
                    int n, int parameter, int threads) {
  size_t len = 0;
  int ok = scalar_base64_decode((const char *)input1, (size_t)n,
                                ((char *)output) + 16, &len);
  uint64_t count = ok ? (uint64_t)len : UINT64_MAX;
  memcpy(output, &count, sizeof(count));
}
