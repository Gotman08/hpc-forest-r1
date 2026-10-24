#include <stddef.h>
#include <stdint.h>
#include <string.h>
#include <omp.h>

#if defined(__GNUC__) && (defined(__x86_64__) || defined(__i386__))
#include <immintrin.h>
#define BASE64_AVX2_INTRINSICS 1
#endif

static const char base64_alphabet[] =
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";

static int base64_value(unsigned char c) {
  if (c >= 'A' && c <= 'Z') return c - 'A';
  if (c >= 'a' && c <= 'z') return c - 'a' + 26;
  if (c >= '0' && c <= '9') return c - '0' + 52;
  if (c == '+') return 62;
  if (c == '/') return 63;
  if (c == '=') return 254;
  return 255;
}

extern "C" void scalar_base64_encode(const char *src, size_t srclen,
                                      char *out, size_t *outlen) {
  const uint8_t *in = (const uint8_t *)src;
  size_t i = 0;
  size_t j = 0;
  while (i + 3 <= srclen) {
    uint32_t v = ((uint32_t)in[i] << 16) | ((uint32_t)in[i + 1] << 8) | in[i + 2];
    out[j++] = base64_alphabet[(v >> 18) & 63];
    out[j++] = base64_alphabet[(v >> 12) & 63];
    out[j++] = base64_alphabet[(v >> 6) & 63];
    out[j++] = base64_alphabet[v & 63];
    i += 3;
  }
  if (i < srclen) {
    uint32_t v = (uint32_t)in[i] << 16;
    out[j++] = base64_alphabet[(v >> 18) & 63];
    if (i + 1 < srclen) {
      v |= (uint32_t)in[i + 1] << 8;
      out[j++] = base64_alphabet[(v >> 12) & 63];
      out[j++] = base64_alphabet[(v >> 6) & 63];
      out[j++] = '=';
    } else {
      out[j++] = base64_alphabet[(v >> 12) & 63];
      out[j++] = '=';
      out[j++] = '=';
    }
  }
  *outlen = j;
}

extern "C" int scalar_base64_decode(const char *src, size_t srclen,
                                     char *out, size_t *outlen) {
  const uint8_t *in = (const uint8_t *)src;
  uint8_t *dst = (uint8_t *)out;
  size_t written = 0;
  if ((srclen & 3) != 0) {
    *outlen = 0;
    return 0;
  }
  for (size_t i = 0; i < srclen; i += 4) {
    int a = base64_value(in[i]);
    int b = base64_value(in[i + 1]);
    int c = base64_value(in[i + 2]);
    int d = base64_value(in[i + 3]);
    int last = (i + 4 == srclen);
    if (a > 63 || b > 63) goto invalid;
    if (c == 254) {
      if (!last || d != 254) goto invalid;
      dst[written++] = (uint8_t)((a << 2) | (b >> 4));
      break;
    }
    if (c > 63) goto invalid;
    if (d == 254) {
      if (!last) goto invalid;
      dst[written++] = (uint8_t)((a << 2) | (b >> 4));
      dst[written++] = (uint8_t)((b << 4) | (c >> 2));
      break;
    }
    if (d > 63) goto invalid;
    dst[written++] = (uint8_t)((a << 2) | (b >> 4));
    dst[written++] = (uint8_t)((b << 4) | (c >> 2));
    dst[written++] = (uint8_t)((c << 6) | d);
  }
  *outlen = written;
  return 1;
invalid:
  *outlen = written;
  return 0;
}

#if defined(BASE64_AVX2_INTRINSICS)
__attribute__((target("avx2")))
static size_t base64_decode_avx2_prefix(const char *src, size_t srclen,
                                        char *out) {
  size_t consumed = 0;
  uint8_t *dst = (uint8_t *)out;
  const __m256i nibble_mask = _mm256_set1_epi8(0x0f);
  const __m256i offset_lut = _mm256_setr_epi8(
      0, 0, 51, 52, -1, 15, 25, 41, 0, 0, 0, 0, 0, 0, 0, 0,
      0, 0, 51, 52, -1, 15, 25, 41, 0, 0, 0, 0, 0, 0, 0, 0);
  const __m256i pair_weights = _mm256_setr_epi8(
      64, 1, 64, 1, 64, 1, 64, 1, 64, 1, 64, 1, 64, 1, 64, 1,
      64, 1, 64, 1, 64, 1, 64, 1, 64, 1, 64, 1, 64, 1, 64, 1);
  const __m256i group_weights = _mm256_setr_epi16(
      4096, 1, 4096, 1, 4096, 1, 4096, 1,
      4096, 1, 4096, 1, 4096, 1, 4096, 1);
  const __m256i output_order = _mm256_setr_epi8(
      2, 1, 0, 6, 5, 4, 10, 9, 8, 14, 13, 12, -1, -1, -1, -1,
      2, 1, 0, 6, 5, 4, 10, 9, 8, 14, 13, 12, -1, -1, -1, -1);

  // Leave the final 32 characters (or fewer) to the scalar padding-aware path.
  while (srclen - consumed > 32) {
    const uint8_t *block = (const uint8_t *)src + consumed;
    const __m256i input = _mm256_loadu_si256((const __m256i *)block);
    const __m256i high = _mm256_and_si256(_mm256_srli_epi16(input, 4), nibble_mask);
    const __m256i low = _mm256_and_si256(input, nibble_mask);
    const __m256i offsets = _mm256_shuffle_epi8(offset_lut, high);
    __m256i values = _mm256_add_epi8(low, offsets);

    const __m256i is_high_2 = _mm256_cmpeq_epi8(high, _mm256_set1_epi8(2));
    const __m256i is_low_15 = _mm256_cmpeq_epi8(low, _mm256_set1_epi8(15));
    const __m256i slash_mask = _mm256_and_si256(is_high_2, is_low_15);
    values = _mm256_sub_epi8(values,
        _mm256_and_si256(slash_mask, _mm256_set1_epi8(3)));

    const __m256i pairs = _mm256_maddubs_epi16(values, pair_weights);
    const __m256i groups = _mm256_madd_epi16(pairs, group_weights);
    const __m256i compact = _mm256_shuffle_epi8(groups, output_order);
    const __m128i lower = _mm256_castsi256_si128(compact);
    const __m128i upper = _mm256_extracti128_si256(compact, 1);

    // A 16-byte store plus bounded 8-byte and 4-byte stores writes exactly 24 bytes.
    _mm_storeu_si128((__m128i *)dst, lower);
    _mm_storel_epi64((__m128i *)(dst + 12), upper);
    const uint32_t last = (uint32_t)_mm_cvtsi128_si32(_mm_srli_si128(upper, 8));
    memcpy(dst + 20, &last, sizeof(last));
    consumed += 32;
    dst += 24;
  }
  return consumed;
}
#endif

extern "C" void run(const void *input1, const void *input2, void *output,
                     int n, int parameter, int threads) {
  size_t len = 0;
  int ok;
#if defined(BASE64_AVX2_INTRINSICS)
  size_t consumed = 0;
  if (n >= 32 && __builtin_cpu_supports("avx2")) {
    consumed = base64_decode_avx2_prefix((const char *)input1, (size_t)n,
                                         (char *)output + 16);
  }
  if (consumed != 0) {
    size_t tail_len = 0;
    ok = scalar_base64_decode((const char *)input1 + consumed,
                              (size_t)n - consumed,
                              (char *)output + 16 + (consumed / 4) * 3,
                              &tail_len);
    len = (consumed / 4) * 3 + tail_len;
  } else {
    ok = scalar_base64_decode((const char *)input1, (size_t)n,
                              (char *)output + 16, &len);
  }
#else
  ok = scalar_base64_decode((const char *)input1, (size_t)n,
                            (char *)output + 16, &len);
#endif
  *(uint64_t *)output = ok ? len : UINT64_MAX;
}
