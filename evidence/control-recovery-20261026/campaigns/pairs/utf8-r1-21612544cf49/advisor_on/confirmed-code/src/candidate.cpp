#include <cstddef>
#include <cstdint>

#if (defined(__GNUC__) || defined(__clang__)) && (defined(__x86_64__) || defined(__i386__))
#include <immintrin.h>
#define UTF8_HAVE_AVX2 1
#define UTF8_AVX2_TARGET __attribute__((target("avx2")))
#else
#define UTF8_HAVE_AVX2 0
#define UTF8_AVX2_TARGET
#endif

static bool is_continuation(unsigned char byte) {
  return (byte & 0xC0) == 0x80;
}

static bool is_lead2(unsigned char byte) {
  return byte >= 0xC2 && byte <= 0xDF;
}

static bool is_lead3(unsigned char byte) {
  return byte >= 0xE0 && byte <= 0xEF;
}

static bool is_lead4(unsigned char byte) {
  return byte >= 0xF0 && byte <= 0xF4;
}

static bool decode_one(const unsigned char *bytes, size_t length, size_t &index) {
  if (index >= length) {
    return false;
  }

  const unsigned char byte1 = bytes[index];
  if (byte1 <= 0x7F) {
    ++index;
    return true;
  }

  if (is_lead2(byte1)) {
    if (length - index < 2 || !is_continuation(bytes[index + 1])) {
      return false;
    }
    index += 2;
    return true;
  }

  if (is_lead3(byte1)) {
    if (length - index < 3) {
      return false;
    }
    const unsigned char byte2 = bytes[index + 1];
    const unsigned char byte3 = bytes[index + 2];
    if (!is_continuation(byte2) || !is_continuation(byte3) ||
        (byte1 == 0xE0 && byte2 < 0xA0) ||
        (byte1 == 0xED && byte2 >= 0xA0)) {
      return false;
    }
    index += 3;
    return true;
  }

  if (is_lead4(byte1)) {
    if (length - index < 4) {
      return false;
    }
    const unsigned char byte2 = bytes[index + 1];
    if (!is_continuation(byte2) ||
        (byte1 == 0xF0 && byte2 < 0x90) ||
        (byte1 == 0xF4 && byte2 > 0x8F) ||
        !is_continuation(bytes[index + 2]) ||
        !is_continuation(bytes[index + 3])) {
      return false;
    }
    index += 4;
    return true;
  }

  return false;
}

static bool validate_scalar(const unsigned char *bytes, size_t length) {
  size_t index = 0;
  while (index < length) {
    if (!decode_one(bytes, length, index)) {
      return false;
    }
  }
  return true;
}

// Return the start of a sequence that still needs bytes at or after index.
static size_t pending_sequence_start(const unsigned char *bytes, size_t index) {
  if (index >= 1 &&
      (is_lead2(bytes[index - 1]) || is_lead3(bytes[index - 1]) ||
       is_lead4(bytes[index - 1]))) {
    return index - 1;
  }
  if (index >= 2 && is_continuation(bytes[index - 1]) &&
      (is_lead3(bytes[index - 2]) || is_lead4(bytes[index - 2]))) {
    return index - 2;
  }
  if (index >= 3 && is_continuation(bytes[index - 1]) &&
      is_continuation(bytes[index - 2]) && is_lead4(bytes[index - 3])) {
    return index - 3;
  }
  return index;
}

#if UTF8_HAVE_AVX2
UTF8_AVX2_TARGET static inline __m256i avx2_byte(unsigned char value) {
  const int signed_value =
      value < 0x80 ? static_cast<int>(value) : static_cast<int>(value) - 0x100;
  return _mm256_set1_epi8(static_cast<char>(signed_value));
}

UTF8_AVX2_TARGET static inline __m256i avx2_u8_gt(__m256i a, __m256i b) {
  const __m256i bias = _mm256_set1_epi8(static_cast<char>(-128));
  return _mm256_cmpgt_epi8(_mm256_xor_si256(a, bias),
                           _mm256_xor_si256(b, bias));
}

UTF8_AVX2_TARGET static inline __m256i avx2_u8_lt(__m256i a, __m256i b) {
  return avx2_u8_gt(b, a);
}

UTF8_AVX2_TARGET static inline __m256i avx2_is_continuation(__m256i value) {
  const __m256i high_bits = avx2_byte(0xC0);
  const __m256i continuation_tag = avx2_byte(0x80);
  return _mm256_cmpeq_epi8(_mm256_and_si256(value, high_bits),
                           continuation_tag);
}

UTF8_AVX2_TARGET static inline __m256i avx2_is_lead2(__m256i value) {
  const __m256i high_bits = avx2_byte(0xE0);
  const __m256i lead_tag = avx2_byte(0xC0);
  return _mm256_cmpeq_epi8(_mm256_and_si256(value, high_bits), lead_tag);
}

UTF8_AVX2_TARGET static inline __m256i avx2_is_lead3(__m256i value) {
  const __m256i high_bits = avx2_byte(0xF0);
  const __m256i lead_tag = avx2_byte(0xE0);
  return _mm256_cmpeq_epi8(_mm256_and_si256(value, high_bits), lead_tag);
}

UTF8_AVX2_TARGET static inline __m256i avx2_is_lead4(__m256i value) {
  const __m256i high_bits = avx2_byte(0xF8);
  const __m256i lead_tag = avx2_byte(0xF0);
  return _mm256_cmpeq_epi8(_mm256_and_si256(value, high_bits), lead_tag);
}

UTF8_AVX2_TARGET static inline __m256i avx2_is_invalid_start(__m256i value) {
  const __m256i clear_low_bit = avx2_byte(0xFE);
  const __m256i c0 = avx2_byte(0xC0);
  const __m256i invalid_c0_c1 = _mm256_cmpeq_epi8(
      _mm256_and_si256(value, clear_low_bit), c0);
  const __m256i invalid_above_f4 = avx2_u8_gt(value, avx2_byte(0xF4));
  return _mm256_or_si256(invalid_c0_c1, invalid_above_f4);
}

// Validate one complete block; the caller checks that it and its history are in bounds.
UTF8_AVX2_TARGET static inline __attribute__((always_inline))
bool validate_avx2_block(const unsigned char *bytes, size_t index) {
  const __m256i current = _mm256_loadu_si256(
      reinterpret_cast<const __m256i *>(bytes + index));

  // Skip all-ASCII blocks before history loads and structural checks.
  if (_mm256_movemask_epi8(current) == 0) {
    return pending_sequence_start(bytes, index) == index;
  }

  const __m256i previous1 = _mm256_loadu_si256(
      reinterpret_cast<const __m256i *>(bytes + index - 1));
  const __m256i previous2 = _mm256_loadu_si256(
      reinterpret_cast<const __m256i *>(bytes + index - 2));
  const __m256i previous3 = _mm256_loadu_si256(
      reinterpret_cast<const __m256i *>(bytes + index - 3));

  const __m256i continuation = avx2_is_continuation(current);
  const __m256i expected_continuation = _mm256_or_si256(
      avx2_is_lead2(previous1),
      _mm256_or_si256(
          _mm256_or_si256(avx2_is_lead3(previous1),
                          avx2_is_lead4(previous1)),
          _mm256_or_si256(
              _mm256_or_si256(avx2_is_lead3(previous2),
                              avx2_is_lead4(previous2)),
              avx2_is_lead4(previous3))));

  __m256i bad = _mm256_xor_si256(continuation, expected_continuation);
  bad = _mm256_or_si256(bad, avx2_is_invalid_start(current));

  // Bounds matter only when a preceding byte is one of the four special leads.
  const __m256i lead_e0 = _mm256_cmpeq_epi8(previous1, avx2_byte(0xE0));
  const __m256i lead_ed = _mm256_cmpeq_epi8(previous1, avx2_byte(0xED));
  const __m256i lead_f0 = _mm256_cmpeq_epi8(previous1, avx2_byte(0xF0));
  const __m256i lead_f4 = _mm256_cmpeq_epi8(previous1, avx2_byte(0xF4));
  const __m256i special_leads = _mm256_or_si256(
      _mm256_or_si256(lead_e0, lead_ed),
      _mm256_or_si256(lead_f0, lead_f4));
  if (_mm256_movemask_epi8(special_leads) != 0) {
    // For valid continuation bytes, signed byte ordering gives the same
    // threshold results; malformed non-continuations are caught structurally.
    const __m256i special_e0 = _mm256_and_si256(
        lead_e0, _mm256_cmpgt_epi8(avx2_byte(0xA0), current));
    const __m256i special_ed = _mm256_and_si256(
        lead_ed, _mm256_cmpgt_epi8(current, avx2_byte(0x9F)));
    const __m256i special_f0 = _mm256_and_si256(
        lead_f0, _mm256_cmpgt_epi8(avx2_byte(0x90), current));
    const __m256i special_f4 = _mm256_and_si256(
        lead_f4, _mm256_cmpgt_epi8(current, avx2_byte(0x8F)));
    bad = _mm256_or_si256(
        bad, _mm256_or_si256(_mm256_or_si256(special_e0, special_ed),
                             _mm256_or_si256(special_f0, special_f4)));
  }

  return _mm256_movemask_epi8(bad) == 0;
}

UTF8_AVX2_TARGET static bool validate_avx2(const unsigned char *bytes,
                                            size_t length) {
  size_t index = 0;

  // Align to a code-point boundary and leave three bytes of safe history.
  while (index < 3 && index < length) {
    if (!decode_one(bytes, length, index)) {
      return false;
    }
  }
  if (index < 3) {
    return validate_scalar(bytes, length);
  }

  // Unroll pairs of full blocks while preserving a bounded single-block loop.
  while (length - index >= 64) {
    if (!validate_avx2_block(bytes, index)) {
      return false;
    }
    index += 32;
    if (!validate_avx2_block(bytes, index)) {
      return false;
    }
    index += 32;
  }

  while (length - index >= 32) {
    if (!validate_avx2_block(bytes, index)) {
      return false;
    }
    index += 32;
  }

  // Restart at an unfinished lead so the scalar suffix checks crossings and
  // the exact end of input without reading beyond it.
  size_t tail = pending_sequence_start(bytes, index);
  while (tail < length) {
    if (!decode_one(bytes, length, tail)) {
      return false;
    }
  }
  return true;
}
#endif

static bool validate_utf8(const char *input, size_t length) {
  const unsigned char *bytes = reinterpret_cast<const unsigned char *>(input);
#if UTF8_HAVE_AVX2
  // A 38-byte minimum covers the maximum six-byte scalar prefix plus one block.
  if (length >= 38 && __builtin_cpu_supports("avx2")) {
    return validate_avx2(bytes, length);
  }
#endif
  return validate_scalar(bytes, length);
}

extern "C" void run(const void *input1, const void *input2, void *output,
                     int n, int parameter, int threads) {
  (void)input2;
  (void)parameter;
  (void)threads;
  uint32_t result = 0;
  if (n >= 0) {
    result = validate_utf8(static_cast<const char *>(input1),
                           static_cast<size_t>(n))
                 ? 1U
                 : 0U;
  }
  *static_cast<uint32_t *>(output) = result;
}
