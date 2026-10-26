#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#if defined(__SSE2__)
#include <emmintrin.h>
#endif
#if (defined(__GNUC__) || defined(__clang__)) && !defined(__INTEL_COMPILER) && (defined(__x86_64__) || defined(__i386__))
#include <immintrin.h>
#define UTF8_HAVE_TARGET_AVX2 1
#else
#define UTF8_HAVE_TARGET_AVX2 0
#endif

static bool is_continuation(unsigned char byte) {
  return (byte & 0xC0) == 0x80;
}

static inline bool valid_special_second(unsigned char lead, unsigned char next) {
  if (lead == 0xE0) return next >= 0xA0;
  if (lead == 0xED) return next <= 0x9F;
  if (lead == 0xF0) return next >= 0x90;
  if (lead == 0xF4) return next <= 0x8F;
  return true;
}

static bool validate_utf8_scalar(const unsigned char *bytes, size_t length) {
  size_t index = 0;
  while (index < length) {
    const unsigned char lead = bytes[index++];
    if (lead < 0x80) continue;

    if (lead <= 0xDF) {
      if (lead < 0xC2 || index == length ||
          !is_continuation(bytes[index])) {
        return false;
      }
      ++index;
    } else if (lead <= 0xEF) {
      if (length - index < 2) return false;
      const unsigned char second = bytes[index];
      if (!is_continuation(second) || !is_continuation(bytes[index + 1]) ||
          !valid_special_second(lead, second)) {
        return false;
      }
      index += 2;
    } else if (lead <= 0xF4) {
      if (length - index < 3) return false;
      const unsigned char second = bytes[index];
      if (!is_continuation(second) || !is_continuation(bytes[index + 1]) ||
          !is_continuation(bytes[index + 2]) ||
          !valid_special_second(lead, second)) {
        return false;
      }
      index += 3;
    } else {
      return false;
    }
  }
  return true;
}

typedef struct {
  unsigned int remaining;
  unsigned char pending_lead;
} Utf8State;

static bool consume_utf8_state_byte(Utf8State *state, unsigned char byte) {
  if (state->remaining != 0) {
    if (!is_continuation(byte) ||
        (state->pending_lead != 0 &&
         !valid_special_second(state->pending_lead, byte))) {
      return false;
    }
    state->pending_lead = 0;
    --state->remaining;
    return true;
  }

  if (byte < 0x80) return true;
  if (byte <= 0xBF || byte < 0xC2) return false;
  if (byte <= 0xDF) {
    state->remaining = 1;
    return true;
  }
  if (byte <= 0xEF) {
    state->remaining = 2;
    state->pending_lead =
        (byte == 0xE0 || byte == 0xED) ? byte : 0;
    return true;
  }
  if (byte <= 0xF4) {
    state->remaining = 3;
    state->pending_lead =
        (byte == 0xF0 || byte == 0xF4) ? byte : 0;
    return true;
  }
  return false;
}

#if defined(__SSE2__)
static inline __m128i unsigned_gt_epi8(__m128i a, __m128i b) {
  const __m128i sign = _mm_set1_epi8((char)0x80);
  return _mm_cmpgt_epi8(_mm_xor_si128(a, sign), _mm_xor_si128(b, sign));
}

static bool validate_utf8_sse2(const unsigned char *bytes, size_t length) {
  size_t index = 0;
  Utf8State state = {0, 0};
  const __m128i all_ones = _mm_set1_epi8((char)0xFF);
  const __m128i continuation_bits = _mm_set1_epi8((char)0xC0);
  const __m128i continuation_value = _mm_set1_epi8((char)0x80);
  const __m128i lead2_bits = _mm_set1_epi8((char)0xE0);
  const __m128i lead2_value = _mm_set1_epi8((char)0xC0);
  const __m128i lead3_bits = _mm_set1_epi8((char)0xF0);
  const __m128i lead3_value = _mm_set1_epi8((char)0xE0);
  const __m128i lead4_bits = _mm_set1_epi8((char)0xF8);
  const __m128i lead4_value = _mm_set1_epi8((char)0xF0);
  const __m128i c1 = _mm_set1_epi8((char)0xC1);
  const __m128i f4 = _mm_set1_epi8((char)0xF4);
  const __m128i e0 = _mm_set1_epi8((char)0xE0);
  const __m128i ed = _mm_set1_epi8((char)0xED);
  const __m128i f0 = _mm_set1_epi8((char)0xF0);
  const __m128i f4_exact = _mm_set1_epi8((char)0xF4);
  const __m128i a0 = _mm_set1_epi8((char)0xA0);
  const __m128i n90 = _mm_set1_epi8((char)0x90);
  const __m128i n9f = _mm_set1_epi8((char)0x9F);
  const __m128i n8f = _mm_set1_epi8((char)0x8F);

  while (length - index >= 16) {
    const __m128i v = _mm_loadu_si128((const __m128i *)(bytes + index));
    const unsigned int high = (unsigned int)_mm_movemask_epi8(v);
    const unsigned int ascii = high ^ 0xFFFFu;
    const __m128i cont_v = _mm_cmpeq_epi8(
        _mm_and_si128(v, continuation_bits), continuation_value);
    const __m128i lead2_v = _mm_and_si128(
        _mm_cmpeq_epi8(_mm_and_si128(v, lead2_bits), lead2_value),
        unsigned_gt_epi8(v, c1));
    const __m128i lead3_v = _mm_cmpeq_epi8(
        _mm_and_si128(v, lead3_bits), lead3_value);
    const __m128i lead4_v = _mm_and_si128(
        _mm_cmpeq_epi8(_mm_and_si128(v, lead4_bits), lead4_value),
        _mm_andnot_si128(unsigned_gt_epi8(v, f4), all_ones));
    const unsigned int cont = (unsigned int)_mm_movemask_epi8(cont_v);
    const unsigned int lead2 = (unsigned int)_mm_movemask_epi8(lead2_v);
    const unsigned int lead3 = (unsigned int)_mm_movemask_epi8(lead3_v);
    const unsigned int lead4 = (unsigned int)_mm_movemask_epi8(lead4_v);

    if ((ascii | cont | lead2 | lead3 | lead4) != 0xFFFFu) return false;

    const __m128i next = _mm_srli_si128(v, 1);
    const __m128i bad_special = _mm_or_si128(
        _mm_or_si128(_mm_and_si128(_mm_cmpeq_epi8(v, e0),
                                   unsigned_gt_epi8(a0, next)),
                     _mm_and_si128(_mm_cmpeq_epi8(v, ed),
                                   unsigned_gt_epi8(next, n9f))),
        _mm_or_si128(_mm_and_si128(_mm_cmpeq_epi8(v, f0),
                                   unsigned_gt_epi8(n90, next)),
                     _mm_and_si128(_mm_cmpeq_epi8(v, f4_exact),
                                   unsigned_gt_epi8(next, n8f))));
    if (((unsigned int)_mm_movemask_epi8(bad_special) & 0x7FFFu) != 0) {
      return false;
    }

    for (unsigned int lane = 0; lane < 16; ++lane) {
      const unsigned int bit = 1u << lane;
      if (state.remaining != 0) {
        if ((cont & bit) == 0) return false;
        if (lane == 0 && state.pending_lead != 0 &&
            !valid_special_second(state.pending_lead, bytes[index])) {
          return false;
        }
        state.pending_lead = 0;
        --state.remaining;
      } else {
        if ((ascii & bit) != 0) continue;
        if ((cont & bit) != 0) return false;

        const unsigned char byte = bytes[index + lane];
        if ((lead2 & bit) != 0) {
          state.remaining = 1;
        } else if ((lead3 & bit) != 0) {
          state.remaining = 2;
        } else if ((lead4 & bit) != 0) {
          state.remaining = 3;
        } else {
          return false;
        }
        state.pending_lead =
            (lane == 15 &&
             (byte == 0xE0 || byte == 0xED || byte == 0xF0 || byte == 0xF4))
                ? byte
                : 0;
      }
    }
    index += 16;
  }

  while (index < length) {
    if (!consume_utf8_state_byte(&state, bytes[index])) return false;
    ++index;
  }
  return state.remaining == 0;
}
#endif

#if UTF8_HAVE_TARGET_AVX2
static __attribute__((target("avx2"))) bool
validate_utf8_avx2(const unsigned char *bytes, size_t length) {
  size_t index = 0;
  unsigned int pending = 0;
  unsigned char pending_lead = 0;
  const __m256i zero = _mm256_setzero_si256();
  const __m256i ones = _mm256_set1_epi8((char)0xFF);

  while (length - index >= 32) {
    if (pending > 3 || (pending_lead != 0 && pending == 0)) return false;
    if (pending_lead != 0) {
      if (!valid_special_second(pending_lead, bytes[index])) return false;
      pending_lead = 0;
    }

    const __m256i block = _mm256_loadu_si256((const __m256i *)(bytes + index));
    const __m256i non_ascii = _mm256_cmpgt_epi8(zero, block);
    const __m256i ascii = _mm256_andnot_si256(non_ascii, ones);
    const __m256i continuation =
        _mm256_cmpgt_epi8(_mm256_set1_epi8(-64), block);
    const __m256i lead2 = _mm256_and_si256(
        _mm256_cmpgt_epi8(block, _mm256_set1_epi8(-63)),
        _mm256_cmpgt_epi8(_mm256_set1_epi8(-32), block));
    const __m256i lead3 = _mm256_and_si256(
        _mm256_cmpgt_epi8(block, _mm256_set1_epi8(-33)),
        _mm256_cmpgt_epi8(_mm256_set1_epi8(-16), block));
    const __m256i lead4 = _mm256_and_si256(
        _mm256_cmpgt_epi8(block, _mm256_set1_epi8(-17)),
        _mm256_cmpgt_epi8(_mm256_set1_epi8(-11), block));

    __m256i classes = _mm256_or_si256(ascii, continuation);
    classes = _mm256_or_si256(classes, lead2);
    classes = _mm256_or_si256(classes, lead3);
    classes = _mm256_or_si256(classes, lead4);
    if (_mm256_movemask_epi8(_mm256_xor_si256(classes, ones)) != 0) {
      return false;
    }

    const unsigned int m2 = (unsigned int)_mm256_movemask_epi8(lead2);
    const unsigned int m3 = (unsigned int)_mm256_movemask_epi8(lead3);
    const unsigned int m4 = (unsigned int)_mm256_movemask_epi8(lead4);
    const unsigned int prefix = pending == 0 ? 0u : ((1u << pending) - 1u);
    const unsigned int expected = (m2 << 1) | (m3 << 1) | (m3 << 2) |
                                  (m4 << 1) | (m4 << 2) | (m4 << 3) | prefix;
    const unsigned int continuation_mask =
        (unsigned int)_mm256_movemask_epi8(continuation);
    if (expected != continuation_mask) return false;

    const __m256i special_leads = _mm256_or_si256(
        _mm256_or_si256(
            _mm256_cmpeq_epi8(block, _mm256_set1_epi8((char)0xE0)),
            _mm256_cmpeq_epi8(block, _mm256_set1_epi8((char)0xED))),
        _mm256_or_si256(
            _mm256_cmpeq_epi8(block, _mm256_set1_epi8((char)0xF0)),
            _mm256_cmpeq_epi8(block, _mm256_set1_epi8((char)0xF4))));
    unsigned int special_lanes =
        (unsigned int)_mm256_movemask_epi8(special_leads);
    pending_lead = 0;
    while (special_lanes != 0) {
      const unsigned int position = (unsigned int)__builtin_ctz(special_lanes);
      const unsigned char lead = bytes[index + position];
      if (position == 31) {
        pending_lead = lead;
      } else if (!valid_special_second(lead, bytes[index + position + 1])) {
        return false;
      }
      special_lanes &= special_lanes - 1u;
    }

    pending = 0;
    if (m4 & 0x80000000u) pending = 3;
    else if (m3 & 0x80000000u) pending = 2;
    else if (m2 & 0x80000000u) pending = 1;
    else if (m4 & 0x40000000u) pending = 2;
    else if (m3 & 0x40000000u) pending = 1;
    else if (m4 & 0x20000000u) pending = 1;
    if (pending == 0) pending_lead = 0;

    index += 32;
  }

  Utf8State state = {pending, pending_lead};
  while (index < length) {
    if (!consume_utf8_state_byte(&state, bytes[index])) return false;
    ++index;
  }
  return state.remaining == 0;
}
#endif

static bool validate_utf8(const char *input, size_t length) {
  const unsigned char *bytes = (const unsigned char *)input;
#if UTF8_HAVE_TARGET_AVX2
  if (length >= 32 && __builtin_cpu_supports("avx2")) {
    return validate_utf8_avx2(bytes, length);
  }
#endif
#if defined(__SSE2__)
  if (length >= 64) return validate_utf8_sse2(bytes, length);
#endif
  return validate_utf8_scalar(bytes, length);
}

#include <cstdint>
#include <cstring>
#include <cmath>
#include <algorithm>
#include <omp.h>
extern "C" void run(const void* input1,const void* input2,void* output,int n,int parameter,int threads)
{*(uint32_t*)output=validate_utf8((const char*)input1,n);}
