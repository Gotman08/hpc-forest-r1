#include <stddef.h>
#include <stdint.h>
#include <string.h>
#include <array>

#if defined(__AVX2__) || defined(_M_AVX2)
#include <immintrin.h>
#define HAVE_AVX2 1
#else
#define HAVE_AVX2 0
#endif

static const char base64_alphabet[] =
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";

static inline unsigned char base64_value(unsigned char c) {
  if (c >= 'A' && c <= 'Z') return (unsigned char)(c - 'A');
  if (c >= 'a' && c <= 'z') return (unsigned char)(c - 'a' + 26);
  if (c >= '0' && c <= '9') return (unsigned char)(c - '0' + 52);
  if (c == '+') return 62;
  if (c == '/') return 63;
  if (c == '=') return 254;
  return 255;
}

static constexpr unsigned char base64_table_entry(unsigned int c) {
  return (c >= 'A' && c <= 'Z') ? (unsigned char)(c - 'A') :
         (c >= 'a' && c <= 'z') ? (unsigned char)(c - 'a' + 26) :
         (c >= '0' && c <= '9') ? (unsigned char)(c - '0' + 52) :
         (c == '+') ? 62 :
         (c == '/') ? 63 :
         (c == '=') ? 254 : 255;
}

static constexpr std::array<unsigned char, 256> make_base64_decode_table() {
  std::array<unsigned char, 256> table{};
  for (unsigned int i = 0; i < 256; ++i) {
    table[i] = base64_table_entry(i);
  }
  return table;
}

static constexpr auto base64_decode_table = make_base64_decode_table();

extern "C" {

int scalar_base64_decode(const char *src, size_t srclen, char *out,
                         size_t *outlen) {
  if (outlen == NULL) return 0;
  *outlen = 0;
  if (srclen == 0) return 1;
  if ((srclen & 3U) != 0) return 0;

  size_t i = 0;
  size_t o = 0;
  while (i < srclen) {
    const unsigned char a = base64_value((unsigned char)src[i]);
    const unsigned char b = base64_value((unsigned char)src[i + 1]);
    const unsigned char c = base64_value((unsigned char)src[i + 2]);
    const unsigned char d = base64_value((unsigned char)src[i + 3]);
    const size_t remaining = srclen - i;

    if (a >= 64 || b >= 64) {
      *outlen = o;
      return 0;
    }
    if (c == 254) {
      if (d != 254 || remaining != 4) {
        *outlen = o;
        return 0;
      }
      out[o++] = (char)((a << 2) | (b >> 4));
      *outlen = o;
      return 1;
    }
    if (c >= 64) {
      *outlen = o;
      return 0;
    }
    if (d == 254) {
      if (remaining != 4) {
        *outlen = o;
        return 0;
      }
      out[o++] = (char)((a << 2) | (b >> 4));
      out[o++] = (char)((b << 4) | (c >> 2));
      *outlen = o;
      return 1;
    }
    if (d >= 64) {
      *outlen = o;
      return 0;
    }

    out[o++] = (char)((a << 2) | (b >> 4));
    out[o++] = (char)((b << 4) | (c >> 2));
    out[o++] = (char)((c << 6) | d);
    i += 4;
  }
  *outlen = o;
  return 1;
}

void scalar_base64_encode(const char *src, size_t srclen, char *out,
                          size_t *outlen) {
  if (outlen == NULL) return;
  size_t i = 0;
  size_t o = 0;
  while (srclen - i >= 3) {
    const unsigned char a = (unsigned char)src[i++];
    const unsigned char b = (unsigned char)src[i++];
    const unsigned char c = (unsigned char)src[i++];
    out[o++] = base64_alphabet[a >> 2];
    out[o++] = base64_alphabet[((a & 3U) << 4) | (b >> 4)];
    out[o++] = base64_alphabet[((b & 15U) << 2) | (c >> 6)];
    out[o++] = base64_alphabet[c & 63U];
  }
  const size_t remaining = srclen - i;
  if (remaining == 1) {
    const unsigned char a = (unsigned char)src[i];
    out[o++] = base64_alphabet[a >> 2];
    out[o++] = base64_alphabet[(a & 3U) << 4];
    out[o++] = '=';
    out[o++] = '=';
  } else if (remaining == 2) {
    const unsigned char a = (unsigned char)src[i];
    const unsigned char b = (unsigned char)src[i + 1];
    out[o++] = base64_alphabet[a >> 2];
    out[o++] = base64_alphabet[((a & 3U) << 4) | (b >> 4)];
    out[o++] = base64_alphabet[(b & 15U) << 2];
    out[o++] = '=';
  }
  *outlen = o;
}

}

static inline size_t decode_valid_suffix(const char *src, size_t srclen,
                                         char *out) {
  size_t i = 0;
  size_t o = 0;

  // The AVX2 caller passes a quartet-aligned suffix of valid Base64 input.
  // Decode complete interior quartets directly into the final output buffer.
  while (srclen - i > 4) {
    const unsigned char a = base64_decode_table[(unsigned char)src[i]];
    const unsigned char b = base64_decode_table[(unsigned char)src[i + 1]];
    const unsigned char c = base64_decode_table[(unsigned char)src[i + 2]];
    const unsigned char d = base64_decode_table[(unsigned char)src[i + 3]];
    out[o++] = (char)((a << 2) | (b >> 4));
    out[o++] = (char)((b << 4) | (c >> 2));
    out[o++] = (char)((c << 6) | d);
    i += 4;
  }

  // The last quartet may be padded; valid input guarantees its shape.
  if (srclen - i == 4) {
    const unsigned char a = base64_decode_table[(unsigned char)src[i]];
    const unsigned char b = base64_decode_table[(unsigned char)src[i + 1]];
    const unsigned char c = base64_decode_table[(unsigned char)src[i + 2]];
    const unsigned char d = base64_decode_table[(unsigned char)src[i + 3]];
    out[o++] = (char)((a << 2) | (b >> 4));
    if (src[i + 2] != '=') {
      out[o++] = (char)((b << 4) | (c >> 2));
      if (src[i + 3] != '=') {
        out[o++] = (char)((c << 6) | d);
      }
    }
  }
  return o;
}

#if HAVE_AVX2
static inline void decode_avx2_block(const char *src, char *out) {
  const __m256i chars = _mm256_loadu_si256((const __m256i *)src);
  const __m256i low_five = _mm256_set1_epi8(0x1f);
  const __m256i low_nibble = _mm256_set1_epi8(0x0f);
  const __m256i offsets = _mm256_setr_epi8(
      0, 0, 0, 36, -1, -1, 25, 25, 0, 0, 0, 0, 0, 0, 0, 0,
      0, 0, 0, 36, -1, -1, 25, 25, 0, 0, 0, 0, 0, 0, 0, 0);
  const __m256i high = _mm256_and_si256(_mm256_srli_epi16(chars, 4), low_nibble);
  __m256i sextets = _mm256_add_epi8(
      _mm256_and_si256(chars, low_five), _mm256_shuffle_epi8(offsets, high));
  sextets = _mm256_blendv_epi8(
      sextets, _mm256_set1_epi8(62),
      _mm256_cmpeq_epi8(chars, _mm256_set1_epi8('+')));
  sextets = _mm256_blendv_epi8(
      sextets, _mm256_set1_epi8(63),
      _mm256_cmpeq_epi8(chars, _mm256_set1_epi8('/')));

  const __m256i pairs = _mm256_maddubs_epi16(
      sextets, _mm256_set1_epi16(0x0140));
  const __m256i words = _mm256_madd_epi16(
      pairs, _mm256_set1_epi32(0x00011000));
  const __m256i compact = _mm256_shuffle_epi8(
      words, _mm256_setr_epi8(
          2, 1, 0, 6, 5, 4, 10, 9, 8, 14, 13, 12, -1, -1, -1, -1,
          2, 1, 0, 6, 5, 4, 10, 9, 8, 14, 13, 12, -1, -1, -1, -1));

  const __m128i low = _mm256_castsi256_si128(compact);
  const __m128i high_lane = _mm256_extracti128_si256(compact, 1);
  const __m128i first16 = _mm_or_si128(low, _mm_slli_si128(high_lane, 12));
  _mm_storeu_si128((__m128i *)out, first16);
  _mm_storel_epi64((__m128i *)(out + 16), _mm_srli_si128(high_lane, 4));
}
#endif

extern "C" void run(const void *input1, const void *input2, void *output,
                     int n, int parameter, int threads) {
  (void)input2;
  (void)parameter;
  (void)threads;
  if (n < 0) {
    const uint64_t invalid_length = UINT64_MAX;
    memcpy(output, &invalid_length, sizeof(invalid_length));
    return;
  }

  const char *src = (const char *)input1;
  char *dst = (char *)output + 16;
  const size_t srclen = (size_t)n;
  size_t decoded_len = 0;
  int ok = 0;

#if HAVE_AVX2
  if (srclen >= 32 && (srclen & 3U) == 0) {
    size_t vector_limit = srclen;
    if (src[srclen - 1] == '=') vector_limit -= 4;

    size_t pos = 0;
    size_t produced = 0;
    for (; pos + 64 <= vector_limit; pos += 64) {
      decode_avx2_block(src + pos, dst + produced);
      decode_avx2_block(src + pos + 32, dst + produced + 24);
      produced += 48;
    }
    for (; pos + 32 <= vector_limit; pos += 32) {
      decode_avx2_block(src + pos, dst + produced);
      produced += 24;
    }

    const size_t tail_len = decode_valid_suffix(
        src + pos, srclen - pos, dst + produced);
    ok = 1;
    decoded_len = produced + tail_len;
  } else {
    ok = scalar_base64_decode(src, srclen, dst, &decoded_len);
  }
#else
  ok = scalar_base64_decode(src, srclen, dst, &decoded_len);
#endif

  const uint64_t result = ok ? (uint64_t)decoded_len : UINT64_MAX;
  memcpy(output, &result, sizeof(result));
}
