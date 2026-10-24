#ifndef SCALAR_B64
#define SCALAR_B64
#include <stddef.h>
#include <stdint.h>
#include <cstring>
#include <cstdint>
#include <cmath>
#include <algorithm>
#include <omp.h>
#ifdef __cplusplus
extern "C" {
#endif
int scalar_base64_decode(const char *src, size_t srclen, char *out, size_t *outlen);
void scalar_base64_encode(const char *src, size_t srclen, char *out, size_t *outlen);
#ifdef __cplusplus
}
#endif
#endif

static const uint8_t base64_table_enc[] = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
static const uint8_t base64_table_dec[] = {
    255,255,255,255,255,255,255,255,255,255,255,255,255,255,255,255,
    255,255,255,255,255,255,255,255,255,255,255,255,255,255,255,255,
    255,255,255,255,255,255,255,255,255,255,255,62,255,255,255,63,
    52,53,54,55,56,57,58,59,60,61,255,255,255,254,255,255,
    255,0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,
    15,16,17,18,19,20,21,22,23,24,25,255,255,255,255,255,
    255,26,27,28,29,30,31,32,33,34,35,36,37,38,39,40,
    41,42,43,44,45,46,47,48,49,50,51,255,255,255,255,255,
    255,255,255,255,255,255,255,255,255,255,255,255,255,255,255,255,
    255,255,255,255,255,255,255,255,255,255,255,255,255,255,255,255,
    255,255,255,255,255,255,255,255,255,255,255,255,255,255,255,255,
    255,255,255,255,255,255,255,255,255,255,255,255,255,255,255,255,
    255,255,255,255,255,255,255,255,255,255,255,255,255,255,255,255,
    255,255,255,255,255,255,255,255,255,255,255,255,255,255,255,255,
    255,255,255,255,255,255,255,255,255,255,255,255,255,255,255,255,
    255,255,255,255,255,255,255,255,255,255,255,255,255,255,255,255};

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

void base64_stream_encode_scalar(struct base64_state *state, const char *src, size_t srclen, char *out, size_t *outlen) {
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

int base64_stream_decode_scalar(struct base64_state *state, const char *src, size_t srclen, char *out, size_t *outlen) {
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
    if (srclen && st.eof == BASE64_AEOF) {
      state->bytes = 0;
      state->eof = BASE64_EOF;
      ret = ((base64_table_dec[*c++] == 254) && (srclen == 1)) ? 1 : 0;
    }
    return ret;
  }
  switch (st.bytes) {
    for (;;) {
    case 0:
      while (srclen >= 13) {
        uint64_t str, res, dec;
        str = *(uint64_t *)c;
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
      if (srclen-- == 0) { ret = 1; break; }
      if ((q = base64_table_dec[*c++]) >= 254) { st.eof = BASE64_EOF; break; }
      st.carry = q << 2;
      st.bytes++;
    case 1:
      if (srclen-- == 0) { ret = 1; break; }
      if ((q = base64_table_dec[*c++]) >= 254) { st.eof = BASE64_EOF; break; }
      *o++ = st.carry | (q >> 4);
      st.carry = q << 4;
      st.bytes++;
      outl++;
    case 2:
      if (srclen-- == 0) { ret = 1; break; }
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
      if (srclen-- == 0) { ret = 1; break; }
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

static void base64_stream_encode_init(struct base64_state *state) { state->eof = 0; state->bytes = 0; state->carry = 0; }
static void base64_stream_encode(struct base64_state *state, const char *src, size_t srclen, char *out, size_t *outlen) { base64_stream_encode_scalar(state, src, srclen, out, outlen); }
static void base64_stream_encode_final(struct base64_state *state, char *out, size_t *outlen) {
  uint8_t *o = (uint8_t *)out;
  if (state->bytes == 1) { *o++ = base64_table_enc[state->carry]; *o++ = '='; *o++ = '='; *outlen = 3; return; }
  if (state->bytes == 2) { *o++ = base64_table_enc[state->carry]; *o++ = '='; *outlen = 2; return; }
  *outlen = 0;
}
static void base64_stream_decode_init(struct base64_state *state) { state->eof = 0; state->bytes = 0; state->carry = 0; }
static int base64_stream_decode(struct base64_state *state, const char *src, size_t srclen, char *out, size_t *outlen) { return base64_stream_decode_scalar(state, src, srclen, out, outlen); }
void scalar_base64_encode(const char *src, size_t srclen, char *out, size_t *outlen) {
  size_t s, t;
  struct base64_state state;
  base64_stream_encode_init(&state);
  base64_stream_encode(&state, src, srclen, out, &s);
  base64_stream_encode_final(&state, out + s, &t);
  *outlen = s + t;
}
static int scalar_base64_decode_reference(const char *src, size_t srclen, char *out, size_t *outlen) {
  int ret;
  struct base64_state state;
  base64_stream_decode_init(&state);
  ret = base64_stream_decode(&state, src, srclen, out, outlen);
  if (ret && state.bytes == 0) return ret;
  return 0;
}

#if (defined(__GNUC__) || defined(__clang__)) && (defined(__x86_64__) || defined(__i386__))
#include <immintrin.h>
#define BASE64_HAS_AVX2_TARGET 1
#define BASE64_AVX2_TARGET __attribute__((target("avx2")))
#else
#define BASE64_HAS_AVX2_TARGET 0
#define BASE64_AVX2_TARGET
#endif

#if BASE64_HAS_AVX2_TARGET
static BASE64_AVX2_TARGET bool base64_decode_block_avx2(const uint8_t *input, uint8_t *output) {
  const __m256i chars = _mm256_loadu_si256(reinterpret_cast<const __m256i *>(input));
  const __m256i upper = _mm256_and_si256(_mm256_cmpgt_epi8(chars, _mm256_set1_epi8('A' - 1)), _mm256_cmpgt_epi8(_mm256_set1_epi8('Z' + 1), chars));
  const __m256i lower = _mm256_and_si256(_mm256_cmpgt_epi8(chars, _mm256_set1_epi8('a' - 1)), _mm256_cmpgt_epi8(_mm256_set1_epi8('z' + 1), chars));
  const __m256i digits = _mm256_and_si256(_mm256_cmpgt_epi8(chars, _mm256_set1_epi8('0' - 1)), _mm256_cmpgt_epi8(_mm256_set1_epi8('9' + 1), chars));
  const __m256i plus = _mm256_cmpeq_epi8(chars, _mm256_set1_epi8('+'));
  const __m256i slash = _mm256_cmpeq_epi8(chars, _mm256_set1_epi8('/'));
  const __m256i valid = _mm256_or_si256(_mm256_or_si256(upper, lower), _mm256_or_si256(digits, _mm256_or_si256(plus, slash)));
  if (_mm256_movemask_epi8(valid) != -1) return false;

  const __m256i offsets = _mm256_or_si256(
      _mm256_or_si256(
          _mm256_and_si256(upper, _mm256_set1_epi8(-65)),
          _mm256_and_si256(lower, _mm256_set1_epi8(-71))),
      _mm256_or_si256(
          _mm256_and_si256(digits, _mm256_set1_epi8(4)),
          _mm256_or_si256(
              _mm256_and_si256(plus, _mm256_set1_epi8(19)),
              _mm256_and_si256(slash, _mm256_set1_epi8(16)))));
  const __m256i sextets = _mm256_add_epi8(chars, offsets);
  const __m256i paired = _mm256_maddubs_epi16(sextets, _mm256_set1_epi16(0x0140));
  const __m256i words = _mm256_madd_epi16(paired, _mm256_set1_epi32(0x00011000));
  const __m256i byte_mask = _mm256_set1_epi32(0xff);
  const __m256i byte0 = _mm256_and_si256(_mm256_srli_epi32(words, 16), byte_mask);
  const __m256i byte1 = _mm256_and_si256(_mm256_srli_epi32(words, 8), byte_mask);
  const __m256i byte2 = _mm256_and_si256(words, byte_mask);
  const __m256i zero = _mm256_setzero_si256();
  const __m256i words01 = _mm256_packus_epi32(byte0, byte1);
  const __m256i words2 = _mm256_packus_epi32(byte2, zero);
  const __m256i planar_bytes = _mm256_packus_epi16(words01, words2);
  const __m256i interleave = _mm256_setr_epi8(0,4,8,1,5,9,2,6,10,3,7,11,-1,-1,-1,-1,0,4,8,1,5,9,2,6,10,3,7,11,-1,-1,-1,-1);
  const __m256i packed = _mm256_shuffle_epi8(planar_bytes, interleave);
  alignas(32) uint8_t temporary[32];
  _mm256_store_si256(reinterpret_cast<__m256i *>(temporary), packed);
  std::memcpy(output, temporary, 12);
  std::memcpy(output + 12, temporary + 16, 12);
  return true;
}
static BASE64_AVX2_TARGET bool base64_decode_blocks_avx2(const uint8_t *input, uint8_t *output, size_t blocks) {
  for (size_t block = 0; block < blocks; ++block) {
    if (!base64_decode_block_avx2(input + block * 32, output + block * 24)) return false;
  }
  return true;
}
#endif

static bool base64_decode_quartets_safely(const char *src, size_t srclen, char *out, size_t *outlen) {
  if ((srclen & 3u) != 0) return false;
  size_t produced_total = 0;
  for (size_t offset = 0; offset < srclen; offset += 4) {
    const bool last_quartet = (srclen - offset == 4);
    if (!last_quartet && (src[offset] == '=' || src[offset + 1] == '=' || src[offset + 2] == '=' || src[offset + 3] == '=')) return false;
    struct base64_state state;
    size_t produced = 0;
    base64_stream_decode_init(&state);
    const int ret = base64_stream_decode(&state, src + offset, 4, out + produced_total, &produced);
    if (!ret || state.bytes != 0 || (!last_quartet && state.eof != 0)) return false;
    produced_total += produced;
  }
  *outlen = produced_total;
  return true;
}

int scalar_base64_decode(const char *src, size_t srclen, char *out, size_t *outlen) {
#if BASE64_HAS_AVX2_TARGET
  if (srclen >= 32) {
    __builtin_cpu_init();
    if (__builtin_cpu_supports("avx2")) {
      size_t padding = 0;
      if (src[srclen - 1] == '=') {
        padding = 1;
        if (srclen >= 2 && src[srclen - 2] == '=') padding = 2;
      }
      const size_t unpadded_length = srclen - padding;
      const size_t vector_length = unpadded_length & ~(size_t)31;
      const size_t blocks = vector_length / 32;
      if (blocks != 0 && base64_decode_blocks_avx2(reinterpret_cast<const uint8_t *>(src), reinterpret_cast<uint8_t *>(out), blocks)) {
        const size_t vector_output_length = (vector_length / 4) * 3;
        size_t tail_output_length = 0;
        if (base64_decode_quartets_safely(src + vector_length, srclen - vector_length, out + vector_output_length, &tail_output_length)) {
          *outlen = vector_output_length + tail_output_length;
          return 1;
        }
      }
    }
  }
#endif
  if (base64_decode_quartets_safely(src, srclen, out, outlen)) return 1;
  return scalar_base64_decode_reference(src, srclen, out, outlen);
}

extern "C" void run(const void *input1, const void *input2, void *output, int n, int parameter, int threads) {
  size_t len = 0;
  int ok = scalar_base64_decode((const char *)input1, n, ((char *)output) + 16, &len);
  *(uint64_t *)output = ok ? len : UINT64_MAX;
}
