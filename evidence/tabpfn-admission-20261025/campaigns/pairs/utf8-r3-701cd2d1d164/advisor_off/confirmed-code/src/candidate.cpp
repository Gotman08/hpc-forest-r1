#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#if (defined(__GNUC__) || defined(__clang__)) && \
    (defined(__i386__) || defined(__x86_64__))
#include <immintrin.h>
#define UTF8_HAVE_TARGET_AVX2 1
#endif

static bool consume_utf8_one(const unsigned char *bytes, size_t length,
                             size_t *position) {
  size_t i = *position;
  if (i >= length) return false;

  unsigned char lead = bytes[i++];
  if (lead < 0x80) {
    *position = i;
    return true;
  }

  if (lead >= 0xC2 && lead <= 0xDF) {
    if (length - i < 1 || (bytes[i] & 0xC0) != 0x80) return false;
    *position = i + 1;
    return true;
  }

  if (lead >= 0xE0 && lead <= 0xEF) {
    if (length - i < 2) return false;
    unsigned char second = bytes[i];
    unsigned char third = bytes[i + 1];
    if ((second & 0xC0) != 0x80 || (third & 0xC0) != 0x80 ||
        (lead == 0xE0 && second < 0xA0) ||
        (lead == 0xED && second >= 0xA0))
      return false;
    *position = i + 2;
    return true;
  }

  if (lead >= 0xF0 && lead <= 0xF4) {
    if (length - i < 3) return false;
    unsigned char second = bytes[i];
    if ((second & 0xC0) != 0x80 ||
        (lead == 0xF0 && second < 0x90) ||
        (lead == 0xF4 && second > 0x8F) ||
        (bytes[i + 1] & 0xC0) != 0x80 ||
        (bytes[i + 2] & 0xC0) != 0x80)
      return false;
    *position = i + 3;
    return true;
  }

  return false;
}

static bool validate_utf8_scalar_from(const unsigned char *bytes,
                                      size_t length, size_t position) {
  while (position < length) {
    if (!consume_utf8_one(bytes, length, &position)) return false;
  }
  return true;
}

static bool validate_utf8_scalar(const unsigned char *bytes, size_t length) {
  return validate_utf8_scalar_from(bytes, length, 0);
}

#ifdef UTF8_HAVE_TARGET_AVX2
static inline __attribute__((target("avx2"), always_inline))
bool validate_avx2_block(const unsigned char *block, uint32_t carry,
                         uint32_t *next_carry) {
  const __m256i v = _mm256_loadu_si256(
      (const __m256i *)(const void *)block);
  const __m256i next = _mm256_loadu_si256(
      (const __m256i *)(const void *)(block + 1));

  const __m256i continuation_bits = _mm256_set1_epi8((char)0xC0);
  const __m256i continuation_value = _mm256_set1_epi8((char)0x80);
  const __m256i c1 = _mm256_set1_epi8((char)0xC1);
  const __m256i df = _mm256_set1_epi8((char)0xDF);
  const __m256i e0 = _mm256_set1_epi8((char)0xE0);
  const __m256i ed = _mm256_set1_epi8((char)0xED);
  const __m256i ef = _mm256_set1_epi8((char)0xEF);
  const __m256i f0 = _mm256_set1_epi8((char)0xF0);
  const __m256i f4 = _mm256_set1_epi8((char)0xF4);
  const __m256i f5 = _mm256_set1_epi8((char)0xF5);
  const __m256i e0_second_mask = _mm256_set1_epi8((char)0xE0);
  const __m256i f0_second_mask = _mm256_set1_epi8((char)0xF0);
  const __m256i second_80 = _mm256_set1_epi8((char)0x80);
  const __m256i second_a0 = _mm256_set1_epi8((char)0xA0);

  const uint32_t high = (uint32_t)_mm256_movemask_epi8(v);
  const uint32_t ascii = ~high;
  const uint32_t continuation = (uint32_t)_mm256_movemask_epi8(
      _mm256_cmpeq_epi8(_mm256_and_si256(v, continuation_bits),
                        continuation_value));
  const uint32_t lead2 = (uint32_t)_mm256_movemask_epi8(
      _mm256_and_si256(_mm256_cmpgt_epi8(v, c1),
                       _mm256_cmpgt_epi8(e0, v)));
  const uint32_t lead3 = (uint32_t)_mm256_movemask_epi8(
      _mm256_and_si256(_mm256_cmpgt_epi8(v, df),
                       _mm256_cmpgt_epi8(f0, v)));
  const uint32_t lead4 = (uint32_t)_mm256_movemask_epi8(
      _mm256_and_si256(_mm256_cmpgt_epi8(v, ef),
                       _mm256_cmpgt_epi8(f5, v)));

  if ((ascii | continuation | lead2 | lead3 | lead4) != UINT32_MAX)
    return false;

  const __m256i bad_e0_second = _mm256_and_si256(
      _mm256_cmpeq_epi8(v, e0),
      _mm256_cmpeq_epi8(_mm256_and_si256(next, e0_second_mask), second_80));
  const __m256i bad_ed_second = _mm256_and_si256(
      _mm256_cmpeq_epi8(v, ed),
      _mm256_cmpeq_epi8(_mm256_and_si256(next, e0_second_mask), second_a0));
  const __m256i bad_f0_second = _mm256_and_si256(
      _mm256_cmpeq_epi8(v, f0),
      _mm256_cmpeq_epi8(_mm256_and_si256(next, f0_second_mask), second_80));
  const __m256i f4_second_allowed = _mm256_cmpeq_epi8(
      _mm256_and_si256(next, f0_second_mask), second_80);
  const __m256i bad_f4_second = _mm256_andnot_si256(
      f4_second_allowed, _mm256_cmpeq_epi8(v, f4));
  if (_mm256_movemask_epi8(bad_e0_second) ||
      _mm256_movemask_epi8(bad_ed_second) ||
      _mm256_movemask_epi8(bad_f0_second) ||
      _mm256_movemask_epi8(bad_f4_second))
    return false;

  uint64_t expected = (uint64_t)carry;
  expected |= (uint64_t)lead2 << 1;
  expected |= (uint64_t)lead3 << 1;
  expected |= (uint64_t)lead3 << 2;
  expected |= (uint64_t)lead4 << 1;
  expected |= (uint64_t)lead4 << 2;
  expected |= (uint64_t)lead4 << 3;
  if (continuation != (uint32_t)expected) return false;
  *next_carry = (uint32_t)(expected >> 32);
  return true;
}

__attribute__((target("avx2")))
static bool validate_utf8_avx2(const unsigned char *bytes, size_t length) {
  size_t position = 0;
  while (position < length && position < 3) {
    if (!consume_utf8_one(bytes, length, &position)) return false;
  }

  uint32_t carry = 0;
  // Process two adjacent blocks per iteration; carry links their masks.
  while (length - position > 64) {
    uint32_t next_carry;
    if (!validate_avx2_block(bytes + position, carry, &next_carry))
      return false;
    carry = next_carry;
    position += 32;

    if (!validate_avx2_block(bytes + position, carry, &next_carry))
      return false;
    carry = next_carry;
    position += 32;
  }

  while (length - position > 32) {
    uint32_t next_carry;
    if (!validate_avx2_block(bytes + position, carry, &next_carry))
      return false;
    carry = next_carry;
    position += 32;
  }

  while (carry != 0) {
    if ((carry & 1u) == 0 || position >= length ||
        (bytes[position] & 0xC0) != 0x80)
      return false;
    ++position;
    carry >>= 1;
  }
  return validate_utf8_scalar_from(bytes, length, position);
}
#endif

static bool validate_utf8(const char *input, size_t length) {
  const unsigned char *bytes = (const unsigned char *)input;
#ifdef UTF8_HAVE_TARGET_AVX2
  __builtin_cpu_init();
  if (__builtin_cpu_supports("avx2"))
    return validate_utf8_avx2(bytes, length);
#endif
  return validate_utf8_scalar(bytes, length);
}

extern "C" void run(const void *input1, const void *input2, void *output,
                     int n, int parameter, int threads) {
  *(uint32_t *)output =
      validate_utf8((const char *)input1, (size_t)n) ? 1u : 0u;
}
