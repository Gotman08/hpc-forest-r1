#include <stddef.h>
#include <stdint.h>
#include <string.h>

#if defined(__GNUC__) && (defined(__x86_64__) || defined(__i386__))
#include <immintrin.h>
#define B64_HAVE_VBMI_IMPL 1
#define B64_TARGET_VBMI __attribute__((target("avx512f,avx512bw,avx512vbmi")))
#else
#define B64_HAVE_VBMI_IMPL 0
#endif

static const char b64_alphabet[] =
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";

static int b64_value(uint8_t c) {
  if (c >= 'A' && c <= 'Z') return c - 'A';
  if (c >= 'a' && c <= 'z') return c - 'a' + 26;
  if (c >= '0' && c <= '9') return c - '0' + 52;
  if (c == '+') return 62;
  if (c == '/') return 63;
  return -1;
}

/* Scalar reference path. It accepts padded input and complete unpadded
 * quartets, matching the decoder's output and return conventions. */
static int scalar_decode(const char *src, size_t srclen, uint8_t *out,
                         size_t *outlen) {
  size_t produced = 0;
  if ((srclen & 3u) != 0) {
    *outlen = 0;
    return 0;
  }

  for (size_t i = 0; i < srclen; i += 4) {
    const uint8_t c0 = (uint8_t)src[i];
    const uint8_t c1 = (uint8_t)src[i + 1];
    const uint8_t c2 = (uint8_t)src[i + 2];
    const uint8_t c3 = (uint8_t)src[i + 3];
    const int a = b64_value(c0);
    const int b = b64_value(c1);
    if (a < 0 || b < 0) {
      *outlen = produced;
      return 0;
    }

    if (c2 == '=') {
      if (i + 4 != srclen || c3 != '=') {
        *outlen = produced;
        return 0;
      }
      out[produced++] = (uint8_t)((a << 2) | (b >> 4));
      continue;
    }

    const int c = b64_value(c2);
    if (c < 0) {
      *outlen = produced;
      return 0;
    }
    if (c3 == '=') {
      if (i + 4 != srclen) {
        *outlen = produced;
        return 0;
      }
      out[produced++] = (uint8_t)((a << 2) | (b >> 4));
      out[produced++] = (uint8_t)((b << 4) | (c >> 2));
      continue;
    }

    const int d = b64_value(c3);
    if (d < 0) {
      *outlen = produced;
      return 0;
    }
    out[produced++] = (uint8_t)((a << 2) | (b >> 4));
    out[produced++] = (uint8_t)((b << 4) | (c >> 2));
    out[produced++] = (uint8_t)((c << 6) | d);
  }

  *outlen = produced;
  return 1;
}

#if B64_HAVE_VBMI_IMPL
/* Direct seven-bit ASCII mapping split across two 64-byte VBMI tables.
 * Unlike the parent's low-six-bit table plus collision corrections, the
 * selected bank distinguishes the ASCII ranges before returning the sextet. */
alignas(64) static const uint8_t b64_ascii_low[64] = {
    0xff, 0,    1,    2,    3,    4,    5,    6,    7,    8,    9,
    10,   11,   12,   13,   14,   15,   16,   17,   18,   19,   20,
    21,   22,   23,   24,   25,   0xff, 0xff, 0xff, 0xff, 0xff,
    0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff,
    0xff, 62,   0xff, 0xff, 0xff, 63,   52,   53,   54,   55,   56,
    57,   58,   59,   60,   61,   0xff, 0xff, 0xff, 0xff, 0xff, 0xff};

alignas(64) static const uint8_t b64_ascii_high[64] = {
    0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff,
    0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff,
    0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff,
    26,   27,   28,   29,   30,   31,   32,   33,   34,   35,   36,   37,
    38,   39,   40,   41,   42,   43,   44,   45,   46,   47,   48,   49,
    50,   51,   0xff, 0xff, 0xff, 0xff, 0xff};

/* Each four-sextet word contains the three decoded bytes in reverse memory
 * order; select them in reverse to emit the original byte order. */
alignas(64) static const uint8_t b64_pack_order[64] = {
    2,  1,  0,  6,  5,  4,  10, 9,  8,  14, 13, 12, 18, 17, 16, 22,
    21, 20, 26, 25, 24, 30, 29, 28, 34, 33, 32, 38, 37, 36, 42, 41,
    40, 46, 45, 44, 50, 49, 48, 54, 53, 52, 58, 57, 56, 62, 61, 60,
    0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0};

B64_TARGET_VBMI
static int decode_vbmi_block(const uint8_t *src, uint8_t *out) {
  const __m512i bytes = _mm512_loadu_si512((const void *)src);
  const __m512i indices =
      _mm512_and_si512(bytes, _mm512_set1_epi8(0x3f));
  const __m512i low_table =
      _mm512_load_si512((const void *)b64_ascii_low);
  const __m512i high_table =
      _mm512_load_si512((const void *)b64_ascii_high);
  const __m512i low_values = _mm512_permutexvar_epi8(indices, low_table);
  const __m512i high_values = _mm512_permutexvar_epi8(indices, high_table);

  const __m512i bit6 =
      _mm512_and_si512(bytes, _mm512_set1_epi8(0x40));
  const __mmask64 upper_bank =
      ~_mm512_cmpeq_epi8_mask(bit6, _mm512_setzero_si512());
  const __m512i values =
      _mm512_mask_mov_epi8(low_values, upper_bank, high_values);

  const __mmask64 invalid_lookup =
      _mm512_cmpeq_epi8_mask(values, _mm512_set1_epi8(-1));
  const __mmask64 non_ascii = _mm512_cmp_epu8_mask(
      bytes, _mm512_set1_epi8(0x7f), _MM_CMPINT_GT);
  if ((invalid_lookup | non_ascii) != 0) return 0;

  /* Pack four 6-bit values into the low 24 bits of each dword. */
  const __m512i sextet_mask = _mm512_set1_epi32(0x3f);
  const __m512i a = _mm512_and_si512(values, sextet_mask);
  const __m512i b =
      _mm512_and_si512(_mm512_srli_epi32(values, 8), sextet_mask);
  const __m512i c =
      _mm512_and_si512(_mm512_srli_epi32(values, 16), sextet_mask);
  const __m512i d =
      _mm512_and_si512(_mm512_srli_epi32(values, 24), sextet_mask);
  const __m512i packed = _mm512_or_si512(
      _mm512_or_si512(_mm512_slli_epi32(a, 18), _mm512_slli_epi32(b, 12)),
      _mm512_or_si512(_mm512_slli_epi32(c, 6), d));

  const __m512i order = _mm512_load_si512((const void *)b64_pack_order);
  const __m512i packed_bytes = _mm512_permutexvar_epi8(order, packed);
  _mm_storeu_si128((__m128i *)(void *)(out),
                   _mm512_castsi512_si128(packed_bytes));
  _mm_storeu_si128((__m128i *)(void *)(out + 16),
                   _mm512_extracti32x4_epi32(packed_bytes, 1));
  _mm_storeu_si128((__m128i *)(void *)(out + 32),
                   _mm512_extracti32x4_epi32(packed_bytes, 2));
  return 1;
}

static int runtime_has_vbmi(void) {
  __builtin_cpu_init();
  return __builtin_cpu_supports("avx512f") &&
         __builtin_cpu_supports("avx512bw") &&
         __builtin_cpu_supports("avx512vbmi");
}
#endif

static int decode_base64(const char *src, size_t srclen, uint8_t *out,
                         size_t *outlen) {
  if ((srclen & 3u) != 0)
    return scalar_decode(src, srclen, out, outlen);
#if B64_HAVE_VBMI_IMPL
  if (srclen >= 64 && runtime_has_vbmi()) {
    size_t vector_end = srclen;
    /* Keep the terminal quartet out of SIMD even when the input ends on a
     * 64-character boundary; it may contain one or two padding characters. */
    if (srclen >= 4 && src[srclen - 1] == '=') vector_end -= 4;

    size_t offset = 0;
    size_t produced = 0;
    while (vector_end - offset >= 64) {
      if (!decode_vbmi_block((const uint8_t *)src + offset, out + produced))
        return scalar_decode(src, srclen, out, outlen);
      offset += 64;
      produced += 48;
    }

    size_t tail_len = 0;
    if (!scalar_decode(src + offset, srclen - offset, out + produced,
                       &tail_len))
      return scalar_decode(src, srclen, out, outlen);
    *outlen = produced + tail_len;
    return 1;
  }
#endif
  return scalar_decode(src, srclen, out, outlen);
}

extern "C" int scalar_base64_decode(const char *src, size_t srclen,
                                     char *out, size_t *outlen) {
  return scalar_decode(src, srclen, (uint8_t *)out, outlen);
}

extern "C" void scalar_base64_encode(const char *src, size_t srclen,
                                      char *out, size_t *outlen) {
  const uint8_t *in = (const uint8_t *)src;
  size_t i = 0;
  size_t produced = 0;
  while (srclen - i >= 3) {
    const uint32_t word = ((uint32_t)in[i] << 16) |
                          ((uint32_t)in[i + 1] << 8) | in[i + 2];
    out[produced++] = b64_alphabet[(word >> 18) & 63];
    out[produced++] = b64_alphabet[(word >> 12) & 63];
    out[produced++] = b64_alphabet[(word >> 6) & 63];
    out[produced++] = b64_alphabet[word & 63];
    i += 3;
  }
  if (srclen - i == 1) {
    const uint32_t word = (uint32_t)in[i] << 16;
    out[produced++] = b64_alphabet[(word >> 18) & 63];
    out[produced++] = b64_alphabet[(word >> 12) & 63];
    out[produced++] = '=';
    out[produced++] = '=';
  } else if (srclen - i == 2) {
    const uint32_t word = ((uint32_t)in[i] << 16) |
                          ((uint32_t)in[i + 1] << 8);
    out[produced++] = b64_alphabet[(word >> 18) & 63];
    out[produced++] = b64_alphabet[(word >> 12) & 63];
    out[produced++] = b64_alphabet[(word >> 6) & 63];
    out[produced++] = '=';
  }
  *outlen = produced;
}

extern "C" void run(const void *input1, const void *input2, void *output,
                    int n, int parameter, int threads) {
  (void)input2;
  (void)parameter;
  (void)threads;

  size_t decoded_len = 0;
  uint64_t result = UINT64_MAX;
  if (n >= 0 && decode_base64((const char *)input1, (size_t)n,
                              (uint8_t *)output + 16, &decoded_len))
    result = (uint64_t)decoded_len;
  memcpy(output, &result, sizeof(result));
}
