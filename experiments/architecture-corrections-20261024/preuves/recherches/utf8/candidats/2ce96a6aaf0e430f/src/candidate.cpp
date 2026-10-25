#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <immintrin.h>
#include <cstdint>
#include <cstring>
#include <cmath>
#include <algorithm>
#include <omp.h>

static bool valid_restricted_second(unsigned char lead, unsigned char second) {
  if (lead == 0xE0) return second >= 0xA0;
  if (lead == 0xED) return second <= 0x9F;
  if (lead == 0xF0) return second >= 0x90;
  if (lead == 0xF4) return second <= 0x8F;
  return true;
}

static bool validate_utf8_scalar(const unsigned char *bytes, size_t length) {
  size_t index = 0;
  while (index < length) {
    const unsigned char lead = bytes[index++];
    if (lead <= 0x7F) continue;

    if (lead >= 0xC2 && lead <= 0xDF) {
      if (index >= length || (bytes[index++] & 0xC0) != 0x80) return false;
      continue;
    }

    if (lead >= 0xE0 && lead <= 0xEF) {
      if (length - index < 2) return false;
      const unsigned char second = bytes[index++];
      if ((second & 0xC0) != 0x80 ||
          !valid_restricted_second(lead, second) ||
          (bytes[index++] & 0xC0) != 0x80) return false;
      continue;
    }

    if (lead >= 0xF0 && lead <= 0xF4) {
      if (length - index < 3) return false;
      const unsigned char second = bytes[index++];
      if ((second & 0xC0) != 0x80 ||
          !valid_restricted_second(lead, second) ||
          (bytes[index++] & 0xC0) != 0x80 ||
          (bytes[index++] & 0xC0) != 0x80) return false;
      continue;
    }

    return false;
  }
  return true;
}

__attribute__((target("avx2")))
static bool validate_utf8_avx2(const unsigned char *bytes, size_t length) {
  size_t index = 0;
  uint32_t pending_continuations = 0;

  // The extra byte makes both scalar checks at the 32-byte chunk boundaries safe.
  while (length - index >= 33) {
    const __m256i chunk = _mm256_loadu_si256(
        reinterpret_cast<const __m256i *>(bytes + index));
    const __m256i shifted = _mm256_srli_si256(chunk, 1);

    const __m256i high_two_bits = _mm256_set1_epi8((char)0xC0);
    const __m256i continuation_value = _mm256_set1_epi8((char)0x80);
    const __m256i continuations = _mm256_cmpeq_epi8(
        _mm256_and_si256(chunk, high_two_bits), continuation_value);
    const __m256i lead2 = _mm256_and_si256(
        _mm256_cmpgt_epi8(chunk, _mm256_set1_epi8((char)0xC1)),
        _mm256_cmpgt_epi8(_mm256_set1_epi8((char)0xE0), chunk));
    const __m256i lead3 = _mm256_and_si256(
        _mm256_cmpgt_epi8(chunk, _mm256_set1_epi8((char)0xDF)),
        _mm256_cmpgt_epi8(_mm256_set1_epi8((char)0xF0), chunk));
    const __m256i lead4 = _mm256_and_si256(
        _mm256_cmpgt_epi8(chunk, _mm256_set1_epi8((char)0xEF)),
        _mm256_cmpgt_epi8(_mm256_set1_epi8((char)0xF5), chunk));

    const uint32_t high_bits = (uint32_t)_mm256_movemask_epi8(chunk);
    const uint32_t continuation_bits =
        (uint32_t)_mm256_movemask_epi8(continuations);
    const uint32_t lead2_bits = (uint32_t)_mm256_movemask_epi8(lead2);
    const uint32_t lead3_bits = (uint32_t)_mm256_movemask_epi8(lead3);
    const uint32_t lead4_bits = (uint32_t)_mm256_movemask_epi8(lead4);

    if (high_bits != (continuation_bits | lead2_bits | lead3_bits | lead4_bits))
      return false;

    const uint64_t leads2 = lead2_bits;
    const uint64_t leads3 = lead3_bits;
    const uint64_t leads4 = lead4_bits;
    const uint64_t expected =
        ((leads2 | leads3 | leads4) << 1) |
        ((leads3 | leads4) << 2) |
        (leads4 << 3);
    const uint32_t expected_here = (uint32_t)expected;
    if (continuation_bits != (expected_here | pending_continuations))
      return false;

    const __m256i e0 = _mm256_cmpeq_epi8(chunk, _mm256_set1_epi8((char)0xE0));
    const __m256i ed = _mm256_cmpeq_epi8(chunk, _mm256_set1_epi8((char)0xED));
    const __m256i f0 = _mm256_cmpeq_epi8(chunk, _mm256_set1_epi8((char)0xF0));
    const __m256i f4 = _mm256_cmpeq_epi8(chunk, _mm256_set1_epi8((char)0xF4));
    const __m256i bad_e0 = _mm256_and_si256(
        e0, _mm256_cmpgt_epi8(_mm256_set1_epi8((char)0xA0), shifted));
    const __m256i bad_ed = _mm256_and_si256(
        ed, _mm256_cmpgt_epi8(shifted, _mm256_set1_epi8((char)0x9F)));
    const __m256i bad_f0 = _mm256_and_si256(
        f0, _mm256_cmpgt_epi8(_mm256_set1_epi8((char)0x90), shifted));
    const __m256i bad_f4 = _mm256_and_si256(
        f4, _mm256_cmpgt_epi8(shifted, _mm256_set1_epi8((char)0x8F)));
    const __m256i bad_restricted = _mm256_or_si256(
        _mm256_or_si256(bad_e0, bad_ed), _mm256_or_si256(bad_f0, bad_f4));
    const uint32_t bad_bits = (uint32_t)_mm256_movemask_epi8(bad_restricted);
    // Byte shifts are lane-local in AVX2; check positions 15 and 31 separately.
    if ((bad_bits & 0x7FFF7FFFu) != 0) return false;

    const __m256i restricted_leads = _mm256_or_si256(
        _mm256_or_si256(e0, ed), _mm256_or_si256(f0, f4));
    const uint32_t restricted_bits =
        (uint32_t)_mm256_movemask_epi8(restricted_leads);
    if ((restricted_bits & (1u << 15)) != 0 &&
        !valid_restricted_second(bytes[index + 15], bytes[index + 16]))
      return false;
    if ((restricted_bits & (1u << 31)) != 0 &&
        !valid_restricted_second(bytes[index + 31], bytes[index + 32]))
      return false;

    pending_continuations = (uint32_t)(expected >> 32);
    index += 32;
  }

  unsigned int pending_count = 0;
  while (pending_count < 3 &&
         (pending_continuations & (1u << pending_count)) != 0)
    ++pending_count;
  if (pending_continuations != ((1u << pending_count) - 1u)) return false;

  for (unsigned int i = 0; i < pending_count; ++i) {
    if (index >= length || (bytes[index] & 0xC0) != 0x80) return false;
    ++index;
  }
  if (index == length) return true;
  return validate_utf8_scalar(bytes + index, length - index);
}

extern "C" void run(const void *input1, const void *input2, void *output,
                    int n, int parameter, int threads) {
  uint32_t result = 0;
  if (n >= 0) {
    result = validate_utf8_avx2((const unsigned char *)input1, (size_t)n) ? 1u : 0u;
  }
  *(uint32_t *)output = result;
}
