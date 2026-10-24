#include <stddef.h>
#include <stdint.h>
#include <string.h>

static int base64_value(unsigned char c) {
  if (c >= 'A' && c <= 'Z') return c - 'A';
  if (c >= 'a' && c <= 'z') return c - 'a' + 26;
  if (c >= '0' && c <= '9') return c - '0' + 52;
  if (c == '+') return 62;
  if (c == '/') return 63;
  return -1;
}

static int scalar_base64_decode(const char *src, size_t srclen, char *out,
                                size_t *outlen) {
  const unsigned char *s = (const unsigned char *)src;
  unsigned char *dst = (unsigned char *)out;
  size_t produced = 0;
  *outlen = 0;

  if (srclen == 0) return 1;
  if ((srclen & 3) != 0) return 0;

  for (size_t i = 0; i < srclen; i += 4) {
    const int last = (i + 4 == srclen);
    const int a = base64_value(s[i]);
    const int b = base64_value(s[i + 1]);
    if (a < 0 || b < 0) return 0;

    if (s[i + 2] == '=') {
      if (!last || s[i + 3] != '=') return 0;
      dst[produced++] = (unsigned char)((a << 2) | (b >> 4));
      continue;
    }

    const int c = base64_value(s[i + 2]);
    if (c < 0) return 0;
    dst[produced++] = (unsigned char)((a << 2) | (b >> 4));
    dst[produced++] = (unsigned char)((b << 4) | (c >> 2));

    if (s[i + 3] == '=') {
      if (!last) return 0;
      continue;
    }

    const int d = base64_value(s[i + 3]);
    if (d < 0) return 0;
    dst[produced++] = (unsigned char)((c << 6) | d);
  }

  *outlen = produced;
  return 1;
}

#if (defined(__GNUC__) || defined(__clang__)) && \\
    (defined(__x86_64__) || defined(__i386__))
#include <immintrin.h>

static inline __attribute__((target("avx2"), always_inline)) void
base64_decode_avx2_block(const uint8_t *src, uint8_t *dst) {
  const __m256i c64 = _mm256_set1_epi8(64);
  const __m256i c65 = _mm256_set1_epi8(65);
  const __m256i c71 = _mm256_set1_epi8(71);
  const __m256i c91 = _mm256_set1_epi8(91);
  const __m256i c96 = _mm256_set1_epi8(96);
  const __m256i c123 = _mm256_set1_epi8(123);
  const __m256i c47 = _mm256_set1_epi8(47);
  const __m256i c58 = _mm256_set1_epi8(58);
  const __m256i plus = _mm256_set1_epi8('+');
  const __m256i slash = _mm256_set1_epi8('/');
  const __m256i offset4 = _mm256_set1_epi8(4);
  const __m256i value62 = _mm256_set1_epi8(62);
  const __m256i value63 = _mm256_set1_epi8(63);
  const __m256i mask0 = _mm256_set1_epi32(0x0000003f);
  const __m256i mask1 = _mm256_set1_epi32(0x00003f00);
  const __m256i mask2 = _mm256_set1_epi32(0x003f0000);
  const __m256i mask3 = _mm256_set1_epi32(0x3f000000);
  const __m256i shuffle = _mm256_setr_epi8(
      2, 1, 0, 6, 5, 4, 10, 9, 8, 14, 13, 12, (char)0x80, (char)0x80,
      (char)0x80, (char)0x80,
      2, 1, 0, 6, 5, 4, 10, 9, 8, 14, 13, 12, (char)0x80, (char)0x80,
      (char)0x80, (char)0x80);

  const __m256i chars = _mm256_loadu_si256((const __m256i *)(const void *)src);
  const __m256i upper = _mm256_and_si256(
      _mm256_cmpgt_epi8(chars, c64), _mm256_cmpgt_epi8(c91, chars));
  const __m256i lower = _mm256_and_si256(
      _mm256_cmpgt_epi8(chars, c96), _mm256_cmpgt_epi8(c123, chars));
  const __m256i digits = _mm256_and_si256(
      _mm256_cmpgt_epi8(chars, c47), _mm256_cmpgt_epi8(c58, chars));
  const __m256i is_plus = _mm256_cmpeq_epi8(chars, plus);
  const __m256i is_slash = _mm256_cmpeq_epi8(chars, slash);

  const __m256i values = _mm256_or_si256(
      _mm256_or_si256(
          _mm256_and_si256(upper, _mm256_sub_epi8(chars, c65)),
          _mm256_and_si256(lower, _mm256_sub_epi8(chars, c71))),
      _mm256_or_si256(
          _mm256_and_si256(digits, _mm256_add_epi8(chars, offset4)),
          _mm256_or_si256(_mm256_and_si256(is_plus, value62),
                          _mm256_and_si256(is_slash, value63))));

  const __m256i packed = _mm256_or_si256(
      _mm256_or_si256(
          _mm256_slli_epi32(_mm256_and_si256(values, mask0), 18),
          _mm256_slli_epi32(_mm256_and_si256(values, mask1), 4)),
      _mm256_or_si256(
          _mm256_srli_epi32(_mm256_and_si256(values, mask2), 10),
          _mm256_srli_epi32(_mm256_and_si256(values, mask3), 24)));
  const __m256i output_bytes = _mm256_shuffle_epi8(packed, shuffle);
  const __m128i low = _mm256_castsi256_si128(output_bytes);
  const __m128i high = _mm256_extracti128_si256(output_bytes, 1);
  uint64_t low8, high8;
  uint32_t low4, high4;
  memcpy(&low8, &low, sizeof(low8));
  memcpy(&low4, (const char *)&low + 8, sizeof(low4));
  memcpy(&high8, &high, sizeof(high8));
  memcpy(&high4, (const char *)&high + 8, sizeof(high4));
  memcpy(dst, &low8, sizeof(low8));
  memcpy(dst + 8, &low4, sizeof(low4));
  memcpy(dst + 12, &high8, sizeof(high8));
  memcpy(dst + 20, &high4, sizeof(high4));
}

static __attribute__((target("avx2"))) int base64_decode_avx2(
    const char *src, size_t srclen, char *out, size_t *outlen, int *handled) {
  *handled = 0;
  if (srclen < 32) return 0;

  const uint8_t *s = (const uint8_t *)src;
  size_t unpadded_len = srclen;
  if (s[srclen - 1] == '=') {
    size_t padding = 1;
    if (srclen > 1 && s[srclen - 2] == '=') padding = 2;
    unpadded_len -= padding;
  }
  const size_t vector_len = unpadded_len & ~(size_t)31;
  if (vector_len == 0) return 0;
  *handled = 1;

  size_t i = 0;
  size_t produced = 0;
  while (vector_len - i >= 128) {
    base64_decode_avx2_block(s + i, (uint8_t *)out + produced);
    base64_decode_avx2_block(s + i + 32, (uint8_t *)out + produced + 24);
    base64_decode_avx2_block(s + i + 64, (uint8_t *)out + produced + 48);
    base64_decode_avx2_block(s + i + 96, (uint8_t *)out + produced + 72);
    i += 128;
    produced += 96;
  }
  if (vector_len - i >= 64) {
    base64_decode_avx2_block(s + i, (uint8_t *)out + produced);
    base64_decode_avx2_block(s + i + 32, (uint8_t *)out + produced + 24);
    i += 64;
    produced += 48;
  }
  if (vector_len - i >= 32) {
    base64_decode_avx2_block(s + i, (uint8_t *)out + produced);
    i += 32;
    produced += 24;
  }

  size_t tail_len = 0;
  int ok = 1;
  if (i < srclen) {
    ok = scalar_base64_decode(src + i, srclen - i, out + produced,
                              &tail_len);
  }
  *outlen = produced + tail_len;
  return ok;
}
#endif

extern "C" void run(const void *input1, const void *input2, void *output,
                    int n, int parameter, int threads) {
  (void)input2;
  (void)parameter;
  (void)threads;
  size_t len = 0;
  int ok;
#if (defined(__GNUC__) || defined(__clang__)) && \\
    (defined(__x86_64__) || defined(__i386__))
  if (__builtin_cpu_supports("avx2")) {
    int handled = 0;
    ok = base64_decode_avx2((const char *)input1, (size_t)n,
                            ((char *)output) + 16, &len, &handled);
    if (!handled) {
      ok = scalar_base64_decode((const char *)input1, (size_t)n,
                                ((char *)output) + 16, &len);
    }
  } else {
    ok = scalar_base64_decode((const char *)input1, (size_t)n,
                              ((char *)output) + 16, &len);
  }
#else
  ok = scalar_base64_decode((const char *)input1, (size_t)n,
                            ((char *)output) + 16, &len);
#endif
  const uint64_t result = ok ? (uint64_t)len : UINT64_MAX;
  memcpy(output, &result, sizeof(result));
}
