#include <stddef.h>
#include <stdint.h>
#include <string.h>

#if defined(__GNUC__) && (defined(__x86_64__) || defined(__i386__))
#include <immintrin.h>
#define BASE64_HAVE_X86_SIMD 1
#else
#define BASE64_HAVE_X86_SIMD 0
#endif

static const uint8_t base64_table_enc[] =
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";

#ifdef __cplusplus
extern "C" {
#endif
int scalar_base64_decode(const char *src, size_t srclen, char *out,
                         size_t *outlen);
void scalar_base64_encode(const char *src, size_t srclen, char *out,
                          size_t *outlen);
#ifdef __cplusplus
}
#endif

#if BASE64_HAVE_X86_SIMD
__attribute__((target("sse2")))
static void base64_emit_12_bytes(uint8_t *dst, __m128i bytes) {
  _mm_storel_epi64((__m128i *)(void *)dst, bytes);
  const uint32_t tail =
      (uint32_t)_mm_cvtsi128_si32(_mm_srli_si128(bytes, 8));
  memcpy(dst + 8, &tail, sizeof(tail));
}

__attribute__((target("avx2")))
static int base64_decode_block_avx2(const uint8_t *src, uint8_t *dst) {
  static const int8_t offsets[32] = {
      0, 0, 16, 4, -65, -65, -71, -71, 0, 0, 0, 0, 0, 0, 0, 0,
      0, 0, 16, 4, -65, -65, -71, -71, 0, 0, 0, 0, 0, 0, 0, 0};
  static const uint8_t shuffle_bytes[32] = {
      2, 1, 0, 0x80, 6, 5, 4, 0x80, 10, 9, 8, 0x80, 14, 13, 12, 0x80,
      2, 1, 0, 0x80, 6, 5, 4, 0x80, 10, 9, 8, 0x80, 14, 13, 12, 0x80};

  const __m256i chars = _mm256_loadu_si256((const __m256i *)(const void *)src);
  const __m256i upper = _mm256_and_si256(
      _mm256_cmpgt_epi8(chars, _mm256_set1_epi8('A' - 1)),
      _mm256_cmpgt_epi8(_mm256_set1_epi8('Z' + 1), chars));
  const __m256i lower = _mm256_and_si256(
      _mm256_cmpgt_epi8(chars, _mm256_set1_epi8('a' - 1)),
      _mm256_cmpgt_epi8(_mm256_set1_epi8('z' + 1), chars));
  const __m256i digits = _mm256_and_si256(
      _mm256_cmpgt_epi8(chars, _mm256_set1_epi8('0' - 1)),
      _mm256_cmpgt_epi8(_mm256_set1_epi8('9' + 1), chars));
  const __m256i plus = _mm256_cmpeq_epi8(chars, _mm256_set1_epi8('+'));
  const __m256i slash = _mm256_cmpeq_epi8(chars, _mm256_set1_epi8('/'));
  const __m256i valid = _mm256_or_si256(
      _mm256_or_si256(upper, lower),
      _mm256_or_si256(digits, _mm256_or_si256(plus, slash)));
  if (_mm256_movemask_epi8(valid) != -1) return 0;

  const __m256i high_nibbles = _mm256_and_si256(
      _mm256_srli_epi32(chars, 4), _mm256_set1_epi8(0x0f));
  const __m256i offset_lut = _mm256_loadu_si256(
      (const __m256i *)(const void *)offsets);
  const __m256i selected_offsets = _mm256_shuffle_epi8(offset_lut, high_nibbles);
  const __m256i plus_adjust = _mm256_and_si256(plus, _mm256_set1_epi8(3));
  const __m256i sextets = _mm256_add_epi8(
      _mm256_add_epi8(chars, selected_offsets), plus_adjust);

  const __m256i pairs = _mm256_maddubs_epi16(
      sextets, _mm256_set1_epi16(0x0140));
  const __m256i words = _mm256_madd_epi16(
      pairs, _mm256_set1_epi32(0x00011000));
  const __m256i mask = _mm256_loadu_si256(
      (const __m256i *)(const void *)shuffle_bytes);
  const __m256i packed = _mm256_shuffle_epi8(words, mask);
  base64_emit_12_bytes(dst, _mm256_castsi256_si128(packed));
  base64_emit_12_bytes(dst + 12, _mm256_extracti128_si256(packed, 1));
  return 1;
}

__attribute__((target("avx512f,avx512bw")))
static int base64_decode_block_avx512(const uint8_t *src, uint8_t *dst) {
  static const int8_t offsets[64] = {
      0, 0, 16, 4, -65, -65, -71, -71, 0, 0, 0, 0, 0, 0, 0, 0,
      0, 0, 16, 4, -65, -65, -71, -71, 0, 0, 0, 0, 0, 0, 0, 0,
      0, 0, 16, 4, -65, -65, -71, -71, 0, 0, 0, 0, 0, 0, 0, 0,
      0, 0, 16, 4, -65, -65, -71, -71, 0, 0, 0, 0, 0, 0, 0, 0};
  static const uint8_t shuffle_bytes[64] = {
      2, 1, 0, 0x80, 6, 5, 4, 0x80, 10, 9, 8, 0x80, 14, 13, 12, 0x80,
      2, 1, 0, 0x80, 6, 5, 4, 0x80, 10, 9, 8, 0x80, 14, 13, 12, 0x80,
      2, 1, 0, 0x80, 6, 5, 4, 0x80, 10, 9, 8, 0x80, 14, 13, 12, 0x80,
      2, 1, 0, 0x80, 6, 5, 4, 0x80, 10, 9, 8, 0x80, 14, 13, 12, 0x80};

  const __m512i chars = _mm512_loadu_si512((const void *)src);
  const __mmask64 upper =
      _mm512_cmpgt_epi8_mask(chars, _mm512_set1_epi8('A' - 1)) &
      _mm512_cmpgt_epi8_mask(_mm512_set1_epi8('Z' + 1), chars);
  const __mmask64 lower =
      _mm512_cmpgt_epi8_mask(chars, _mm512_set1_epi8('a' - 1)) &
      _mm512_cmpgt_epi8_mask(_mm512_set1_epi8('z' + 1), chars);
  const __mmask64 digits =
      _mm512_cmpgt_epi8_mask(chars, _mm512_set1_epi8('0' - 1)) &
      _mm512_cmpgt_epi8_mask(_mm512_set1_epi8('9' + 1), chars);
  const __mmask64 plus = _mm512_cmpeq_epi8_mask(chars, _mm512_set1_epi8('+'));
  const __mmask64 slash = _mm512_cmpeq_epi8_mask(chars, _mm512_set1_epi8('/'));
  const __mmask64 valid = upper | lower | digits | plus | slash;
  if (valid != (__mmask64)~(__mmask64)0) return 0;

  const __m512i high_nibbles = _mm512_and_si512(
      _mm512_srli_epi32(chars, 4), _mm512_set1_epi8(0x0f));
  const __m512i offset_lut = _mm512_loadu_si512((const void *)offsets);
  const __m512i selected_offsets = _mm512_shuffle_epi8(offset_lut, high_nibbles);
  const __m512i plus_adjust = _mm512_maskz_mov_epi8(
      plus, _mm512_set1_epi8(3));
  const __m512i sextets = _mm512_add_epi8(
      _mm512_add_epi8(chars, selected_offsets), plus_adjust);

  const __m512i pairs = _mm512_maddubs_epi16(
      sextets, _mm512_set1_epi16(0x0140));
  const __m512i words = _mm512_madd_epi16(
      pairs, _mm512_set1_epi32(0x00011000));
  const __m512i mask = _mm512_loadu_si512((const void *)shuffle_bytes);
  const __m512i packed = _mm512_shuffle_epi8(words, mask);
  base64_emit_12_bytes(dst, _mm512_castsi512_si128(packed));
  base64_emit_12_bytes(dst + 12, _mm512_extracti32x4_epi32(packed, 1));
  base64_emit_12_bytes(dst + 24, _mm512_extracti32x4_epi32(packed, 2));
  base64_emit_12_bytes(dst + 36, _mm512_extracti32x4_epi32(packed, 3));
  return 1;
}
#endif

static int base64_value(uint8_t c) {
  if (c >= 'A' && c <= 'Z') return (int)(c - 'A');
  if (c >= 'a' && c <= 'z') return (int)(c - 'a') + 26;
  if (c >= '0' && c <= '9') return (int)(c - '0') + 52;
  if (c == '+') return 62;
  if (c == '/') return 63;
  return -1;
}

static size_t base64_decode_simd_blocks(const uint8_t *src, size_t srclen,
                                        uint8_t *dst) {
  size_t consumed = 0;
#if BASE64_HAVE_X86_SIMD
  if (srclen < 32) return 0;
  __builtin_cpu_init();
  if (__builtin_cpu_supports("avx512f") &&
      __builtin_cpu_supports("avx512bw")) {
    while (srclen - consumed >= 64) {
      if (!base64_decode_block_avx512(src + consumed,
                                      dst + (consumed / 4) * 3))
        break;
      consumed += 64;
    }
  }
  if (__builtin_cpu_supports("avx2")) {
    while (srclen - consumed >= 32) {
      if (!base64_decode_block_avx2(src + consumed,
                                    dst + (consumed / 4) * 3))
        break;
      consumed += 32;
    }
  }
#else
  (void)src;
  (void)srclen;
  (void)dst;
#endif
  return consumed;
}

int scalar_base64_decode(const char *src, size_t srclen, char *out,
                         size_t *outlen) {
  const uint8_t *input = (const uint8_t *)src;
  uint8_t *output = (uint8_t *)out;
  size_t i = 0;
  size_t outpos = 0;
  *outlen = 0;
  if (srclen == 0) return 1;

  const size_t simd_in = base64_decode_simd_blocks(input, srclen, output);
  i = simd_in;
  outpos = (simd_in / 4) * 3;

  while (srclen - i >= 4) {
    const size_t remaining = srclen - i;
    const uint8_t c0 = input[i];
    const uint8_t c1 = input[i + 1];
    const uint8_t c2 = input[i + 2];
    const uint8_t c3 = input[i + 3];
    const int v0 = base64_value(c0);
    const int v1 = base64_value(c1);
    if (v0 < 0 || v1 < 0) return 0;

    if (c2 == '=') {
      if (c3 != '=' || remaining != 4) return 0;
      output[outpos++] = (uint8_t)((v0 << 2) | (v1 >> 4));
      *outlen = outpos;
      return 1;
    }
    const int v2 = base64_value(c2);
    if (v2 < 0) return 0;
    output[outpos++] = (uint8_t)((v0 << 2) | (v1 >> 4));

    if (c3 == '=') {
      if (remaining != 4) return 0;
      output[outpos++] = (uint8_t)((v1 << 4) | (v2 >> 2));
      *outlen = outpos;
      return 1;
    }
    const int v3 = base64_value(c3);
    if (v3 < 0) return 0;
    output[outpos++] = (uint8_t)((v1 << 4) | (v2 >> 2));
    output[outpos++] = (uint8_t)((v2 << 6) | v3);
    i += 4;
  }

  const size_t remaining = srclen - i;
  if (remaining == 2 || remaining == 3) {
    const int v0 = base64_value(input[i]);
    const int v1 = base64_value(input[i + 1]);
    if (v0 < 0 || v1 < 0) return 0;
    output[outpos++] = (uint8_t)((v0 << 2) | (v1 >> 4));
    if (remaining == 3) {
      const int v2 = base64_value(input[i + 2]);
      if (v2 < 0) return 0;
      output[outpos++] = (uint8_t)((v1 << 4) | (v2 >> 2));
    }
  } else if (remaining != 0) {
    return 0;
  }

  *outlen = outpos;
  return 1;
}

void scalar_base64_encode(const char *src, size_t srclen, char *out,
                          size_t *outlen) {
  const uint8_t *input = (const uint8_t *)src;
  uint8_t *output = (uint8_t *)out;
  size_t i = 0;
  size_t outpos = 0;
  while (srclen - i >= 3) {
    const uint32_t value = ((uint32_t)input[i] << 16) |
                           ((uint32_t)input[i + 1] << 8) |
                           (uint32_t)input[i + 2];
    output[outpos++] = base64_table_enc[(value >> 18) & 63];
    output[outpos++] = base64_table_enc[(value >> 12) & 63];
    output[outpos++] = base64_table_enc[(value >> 6) & 63];
    output[outpos++] = base64_table_enc[value & 63];
    i += 3;
  }
  if (srclen - i == 1) {
    const uint32_t value = (uint32_t)input[i] << 16;
    output[outpos++] = base64_table_enc[(value >> 18) & 63];
    output[outpos++] = base64_table_enc[(value >> 12) & 63];
    output[outpos++] = '=';
    output[outpos++] = '=';
  } else if (srclen - i == 2) {
    const uint32_t value = ((uint32_t)input[i] << 16) |
                           ((uint32_t)input[i + 1] << 8);
    output[outpos++] = base64_table_enc[(value >> 18) & 63];
    output[outpos++] = base64_table_enc[(value >> 12) & 63];
    output[outpos++] = base64_table_enc[(value >> 6) & 63];
    output[outpos++] = '=';
  }
  *outlen = outpos;
}

extern "C" void run(const void *input1, const void *input2, void *output,
                    int n, int parameter, int threads) {
  (void)input2;
  (void)parameter;
  (void)threads;
  size_t len = 0;
  const int ok = n >= 0 && scalar_base64_decode(
      (const char *)input1, (size_t)n, (char *)output + 16, &len);
  *(uint64_t *)output = ok ? (uint64_t)len : UINT64_MAX;
}
