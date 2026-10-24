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
/* The low-six-bit table directly maps letters. Digits and the two special
 * characters share low-six-bit indices with letters, so masks add corrections. */
alignas(64) static const uint8_t b64_low6_table[64] = {
    0,  0,  1,  2,  3,  4,  5,  6,  7,  8,  9,  10, 11, 12, 13, 14,
    15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 0,  0,  0,  0,  0,
    0,  26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40,
    41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51, 0,  0,  0,  0,  0};

B64_TARGET_VBMI
static int decode_vbmi_block(const uint8_t *src, uint8_t *out) {
  const __m512i bytes = _mm512_loadu_si512((const void *)src);
  const __m512i lut = _mm512_load_si512((const void *)b64_low6_table);
  const __m512i low6 = _mm512_and_si512(bytes, _mm512_set1_epi8(0x3f));

  const __m512i upper_a = _mm512_set1_epi8('A');
  const __m512i upper_z = _mm512_set1_epi8('Z');
  const __m512i lower_a = _mm512_set1_epi8('a');
  const __m512i lower_z = _mm512_set1_epi8('z');
  const __m512i digit_0 = _mm512_set1_epi8('0');
  const __m512i digit_9 = _mm512_set1_epi8('9');
  const __mmask64 upper =
      _mm512_cmp_epu8_mask(bytes, upper_a, _MM_CMPINT_NLT) &
      _mm512_cmp_epu8_mask(bytes, upper_z, _MM_CMPINT_LE);
  const __mmask64 lower =
      _mm512_cmp_epu8_mask(bytes, lower_a, _MM_CMPINT_NLT) &
      _mm512_cmp_epu8_mask(bytes, lower_z, _MM_CMPINT_LE);
  const __mmask64 digits =
      _mm512_cmp_epu8_mask(bytes, digit_0, _MM_CMPINT_NLT) &
      _mm512_cmp_epu8_mask(bytes, digit_9, _MM_CMPINT_LE);
  const __mmask64 plus = _mm512_cmpeq_epi8_mask(bytes, _mm512_set1_epi8('+'));
  const __mmask64 slash = _mm512_cmpeq_epi8_mask(bytes, _mm512_set1_epi8('/'));
  const __mmask64 valid = upper | lower | digits | plus | slash;
  if (valid != (__mmask64)UINT64_MAX) return 0;

  __m512i values = _mm512_permutexvar_epi8(low6, lut);
  values = _mm512_mask_add_epi8(values, digits, values, _mm512_set1_epi8(11));
  values = _mm512_mask_add_epi8(values, plus, values, _mm512_set1_epi8(26));
  values = _mm512_mask_add_epi8(values, slash, values, _mm512_set1_epi8(23));

  alignas(64) uint8_t mapped[64];
  _mm512_store_si512((void *)mapped, values);
  size_t p = 0;
  for (size_t group = 0; group < 16; ++group) {
    const unsigned int a = mapped[4 * group];
    const unsigned int b = mapped[4 * group + 1];
    const unsigned int c = mapped[4 * group + 2];
    const unsigned int d = mapped[4 * group + 3];
    out[p++] = (uint8_t)((a << 2) | (b >> 4));
    out[p++] = (uint8_t)((b << 4) | (c >> 2));
    out[p++] = (uint8_t)((c << 6) | d);
  }
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
