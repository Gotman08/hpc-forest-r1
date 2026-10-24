#include <stddef.h>
#include <stdint.h>

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
/* Pack four sextets into a 24-bit word; emit its three bytes in order. */
static inline __attribute__((always_inline)) void
base64_emit_words(const uint32_t *words, size_t count, uint8_t *dst) {
  for (size_t i = 0; i < count; ++i) {
    const uint32_t word = words[i];
    dst[3 * i] = (uint8_t)(word >> 16);
    dst[3 * i + 1] = (uint8_t)(word >> 8);
    dst[3 * i + 2] = (uint8_t)word;
  }
}

__attribute__((target("avx2"), always_inline))
static inline int base64_decode_block_avx2(const uint8_t *src, uint8_t *dst) {
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

  __m256i sextets = _mm256_and_si256(
      _mm256_sub_epi8(chars, _mm256_set1_epi8('A')), upper);
  sextets = _mm256_or_si256(sextets, _mm256_and_si256(
      _mm256_add_epi8(_mm256_sub_epi8(chars, _mm256_set1_epi8('a')),
                      _mm256_set1_epi8(26)), lower));
  sextets = _mm256_or_si256(sextets, _mm256_and_si256(
      _mm256_add_epi8(_mm256_sub_epi8(chars, _mm256_set1_epi8('0')),
                      _mm256_set1_epi8(52)), digits));
  sextets = _mm256_or_si256(
      sextets, _mm256_and_si256(plus, _mm256_set1_epi8(62)));
  sextets = _mm256_or_si256(
      sextets, _mm256_and_si256(slash, _mm256_set1_epi8(63)));

  const __m256i pairs = _mm256_maddubs_epi16(
      sextets, _mm256_set1_epi16(0x0140));
  const __m256i words = _mm256_madd_epi16(
      pairs, _mm256_set1_epi32(0x00011000));
  uint32_t packed[8];
  _mm256_storeu_si256((__m256i *)(void *)packed, words);
  base64_emit_words(packed, 8, dst);
  return 1;
}

__attribute__((target("avx512f,avx512bw"), always_inline))
static inline int base64_decode_block_avx512(const uint8_t *src,
                                             uint8_t *dst) {
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

  __m512i sextets = _mm512_maskz_mov_epi8(
      upper, _mm512_sub_epi8(chars, _mm512_set1_epi8('A')));
  sextets = _mm512_or_si512(sextets, _mm512_maskz_mov_epi8(
      lower, _mm512_add_epi8(
          _mm512_sub_epi8(chars, _mm512_set1_epi8('a')),
          _mm512_set1_epi8(26))));
  sextets = _mm512_or_si512(sextets, _mm512_maskz_mov_epi8(
      digits, _mm512_add_epi8(
          _mm512_sub_epi8(chars, _mm512_set1_epi8('0')),
          _mm512_set1_epi8(52))));
  sextets = _mm512_or_si512(sextets, _mm512_maskz_mov_epi8(
      plus, _mm512_set1_epi8(62)));
  sextets = _mm512_or_si512(sextets, _mm512_maskz_mov_epi8(
      slash, _mm512_set1_epi8(63)));

  const __m512i pairs = _mm512_maddubs_epi16(
      sextets, _mm512_set1_epi16(0x0140));
  const __m512i words = _mm512_madd_epi16(
      pairs, _mm512_set1_epi32(0x00011000));
  uint32_t packed[16];
  _mm512_storeu_si512((void *)packed, words);
  base64_emit_words(packed, 16, dst);
  return 1;
}

/* Amortize the target-function boundary across all complete blocks. */
__attribute__((target("avx2")))
static size_t base64_decode_blocks_avx2(const uint8_t *src, size_t srclen,
                                        uint8_t *dst) {
  size_t consumed = 0;
  while (srclen - consumed >= 32) {
    if (!base64_decode_block_avx2(
            src + consumed, dst + (consumed / 4) * 3))
      break;
    consumed += 32;
  }
  return consumed;
}

__attribute__((target("avx512f,avx512bw")))
static size_t base64_decode_blocks_avx512(const uint8_t *src, size_t srclen,
                                          uint8_t *dst) {
  size_t consumed = 0;
  while (srclen - consumed >= 64) {
    if (!base64_decode_block_avx512(
            src + consumed, dst + (consumed / 4) * 3))
      break;
    consumed += 64;
  }
  return consumed;
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
  __builtin_cpu_init();
  /* Reserve AVX-512 for inputs with at least 16 complete wide blocks. */
  const size_t avx512_min_bytes = 16u * 64u;
  if (srclen >= avx512_min_bytes && __builtin_cpu_supports("avx512f") &&
      __builtin_cpu_supports("avx512bw")) {
    consumed = base64_decode_blocks_avx512(src, srclen, dst);
  }
  if (srclen - consumed >= 32 && __builtin_cpu_supports("avx2")) {
    consumed += base64_decode_blocks_avx2(
        src + consumed, srclen - consumed, dst + (consumed / 4) * 3);
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
