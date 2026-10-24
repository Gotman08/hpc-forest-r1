#ifndef SCALAR_B64
#define SCALAR_B64

/**
* Assumes recent x64 hardware with AVX2 instructions.
*/

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif /* __cplusplus */

/**
* We copy the code below from https://github.com/aklomp/base64
**/


/* Wrapper function to decode a plain string of given length. Output is written
 * to *out without trailing zero. Output length in bytes is written to *outlen.
 * The buffer in `out` has been allocated by the caller and is at least 3/4 the
 * size of the input. */
int scalar_base64_decode
	( const char		*src
	, size_t		 srclen
	, char			*out
	, size_t		*outlen
	) ;


/* Wrapper function to encode a plain string of given length. Output is written
 * to *out without trailing zero. Output length in bytes is written to *outlen.
 * The buffer in `out` has been allocated by the caller and is at least 4/3 the
 * size of the input.  */
void scalar_base64_encode
	( const char		*src
	, size_t		 srclen
	, char			*out
	, size_t		*outlen
	) ;

#ifdef __cplusplus
}
#endif /* __cplusplus */

#endif



/**
* We copy the code below from https://github.com/aklomp/base64
* We specialize it for 64-bit scalar processing.
**/


static const uint8_t base64_table_enc[] = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
                                   "abcdefghijklmnopqrstuvwxyz"
                                   "0123456789+/";


// In the lookup table below, note that the value for '=' (character 61) is
// 254, not 255. This character is used for in-band signaling of the end of
// the datastream, and we will use that later. The characters A-Z, a-z, 0-9
// and + / are mapped to their "decoded" values. The other bytes all map to
// the value 255, which flags them as "invalid input".


static
const uint8_t base64_table_dec[] = {
    255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255,
    255, 255, //   0..15
    255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255,
    255, 255, //  16..31
    255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255,
    255, 255, //  32..47
    52,  53,  54,  55,  56,  57,  58,  59,  60,  61,  255, 255, 255, 254,
    255, 255, //  48..63
    255, 0,   1,   2,   3,   4,   5,   6,   7,   8,   9,   10,  11,  12,
    13,  14, //  64..79
    15,  16,  17,  18,  19,  20,  21,  22,  23,  24,  25,  255, 255, 255,
    255, 255, //  80..95
    255, 26,  27,  28,  29,  30,  31,  32,  33,  34,  35,  36,  37,  38,
    39,  40, //  96..111
    41,  42,  43,  44,  45,  46,  47,  48,  49,  50,  51,  255, 255, 255,
    255, 255, // 112..127
    255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255,
    255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255,
    255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255,
    255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255,
    255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255,
    255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255,
    255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255,
    255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255,
};




struct base64_state {
	int eof;
	int bytes;
	//int flags;// unused
	unsigned char carry;
};
// Cast away unused variable, silence compiler:
#define UNUSED(x) ((void)(x))

// Stub function when encoder arch unsupported:
#define BASE64_ENC_STUB                                                        \
  UNUSED(state);                                                               \
  UNUSED(src);                                                                 \
  UNUSED(srclen);                                                              \
  UNUSED(out);                                                                 \
                                                                               \
  *outlen = 0;

// Stub function when decoder arch unsupported:
#define BASE64_DEC_STUB                                                        \
  UNUSED(state);                                                               \
  UNUSED(src);                                                                 \
  UNUSED(srclen);                                                              \
  UNUSED(out);                                                                 \
  UNUSED(outlen);                                                              \
                                                                               \
  return -1;

struct codec {
  void (*enc)(struct base64_state *state, const char *src, size_t srclen,
              char *out, size_t *outlen);
  int (*dec)(struct base64_state *state, const char *src, size_t srclen,
             char *out, size_t *outlen);
};

// Define machine endianness. This is for GCC:
#if (__BYTE_ORDER__ == __ORDER_LITTLE_ENDIAN__)
#define BASE64_LITTLE_ENDIAN 1
#else
#define BASE64_LITTLE_ENDIAN 0
#endif

// This is for Clang:
#ifdef __LITTLE_ENDIAN__
#define BASE64_LITTLE_ENDIAN 1
#endif

#ifdef __BIG_ENDIAN__
#define BASE64_LITTLE_ENDIAN 0
#endif

// Endian conversion functions:
#if BASE64_LITTLE_ENDIAN
#if defined(_MSC_VER)
// Microsoft Visual C++:
#define cpu_to_be32(x) _byteswap_ulong(x)
#define cpu_to_be64(x) _byteswap_uint64(x)
#define be32_to_cpu(x) _byteswap_ulong(x)
#define be64_to_cpu(x) _byteswap_uint64(x)
#else
// GCC and Clang:
#define cpu_to_be32(x) __builtin_bswap32(x)
#define cpu_to_be64(x) __builtin_bswap64(x)
#define be32_to_cpu(x) __builtin_bswap32(x)
#define be64_to_cpu(x) __builtin_bswap64(x)
#endif
#else
// No conversion needed:
#define cpu_to_be32(x) (x)
#define cpu_to_be64(x) (x)
#define be32_to_cpu(x) (x)
#define be64_to_cpu(x) (x)
#endif

// detect word size
#ifdef _INTEGRAL_MAX_BITS
#define BASE64_WORDSIZE _INTEGRAL_MAX_BITS
#else
#define BASE64_WORDSIZE __WORDSIZE
#endif

// end-of-file definitions
// Almost end-of-file when waiting for the last '=' character:
#define BASE64_AEOF 1
// End-of-file when stream end has been reached or invalid input provided:
#define BASE64_EOF 2



void base64_stream_encode_scalar(struct base64_state *state, const char *src,
                               size_t srclen, char *out, size_t *outlen) {
  // Assume that *out is large enough to contain the output.
  // Theoretically it should be 4/3 the size of src.
  const uint8_t *c = (const uint8_t *)src;
  uint8_t *o = (uint8_t *)out;

  // Use local temporaries to avoid cache thrashing:
  size_t outl = 0;
  struct base64_state st;
  st.bytes = state->bytes;
  st.carry = state->carry;

  // Turn three bytes into four 6-bit numbers:
  // in[0] = 00111111
  // in[1] = 00112222
  // in[2] = 00222233
  // in[3] = 00333333

  // Duff's device, a for() loop inside a switch() statement. Legal!
  switch (st.bytes) {
    for (;;) {
    case 0:
// If we have 64-bit ints, pick off 6 bytes at a time for as long as we can,
// but ensure that there are at least 8 bytes available to avoid segfaulting:
while (srclen >= 8)
{
	// Load string:
	uint64_t str = *(uint64_t *)c;

	// Reorder to 64-bit big-endian, if not already in that format. The
	// workset must be in big-endian, otherwise the shifted bits do not
	// carry over properly among adjacent bytes:
	str = cpu_to_be64(str);

	// Shift input by 6 bytes each round and mask in only the lower 6 bits;
	// look up the character in the Base64 encoding table and write it to
	// the output location:
	*o++ = base64_table_enc[(str >> 58) & 0x3F];
	*o++ = base64_table_enc[(str >> 52) & 0x3F];
	*o++ = base64_table_enc[(str >> 46) & 0x3F];
	*o++ = base64_table_enc[(str >> 40) & 0x3F];
	*o++ = base64_table_enc[(str >> 34) & 0x3F];
	*o++ = base64_table_enc[(str >> 28) & 0x3F];
	*o++ = base64_table_enc[(str >> 22) & 0x3F];
	*o++ = base64_table_enc[(str >> 16) & 0x3F];

	c += 6;	// 6 bytes of input
	outl += 8;	// 8 bytes of output
	srclen -= 6;
}

      if (srclen-- == 0) {
        break;
      }
      *o++ = base64_table_enc[*c >> 2];
      st.carry = (*c++ << 4) & 0x30;
      st.bytes++;
      outl += 1;

    case 1:
      if (srclen-- == 0) {
        break;
      }
      *o++ = base64_table_enc[st.carry | (*c >> 4)];
      st.carry = (*c++ << 2) & 0x3C;
      st.bytes++;
      outl += 1;

    case 2:
      if (srclen-- == 0) {
        break;
      }
      *o++ = base64_table_enc[st.carry | (*c >> 6)];
      *o++ = base64_table_enc[*c++ & 0x3F];
      st.bytes = 0;
      outl += 2;
    }
  }
  state->bytes = st.bytes;
  state->carry = st.carry;
  *outlen = outl;
}

int base64_stream_decode_scalar(struct base64_state *state, const char *src,
                              size_t srclen, char *out, size_t *outlen) {
  int ret = 0;
  const uint8_t *c = (const uint8_t *)src;
  uint8_t *o = (uint8_t *)out;
  uint8_t q;

  // Use local temporaries to avoid cache thrashing:
  size_t outl = 0;
  struct base64_state st;
  st.eof = state->eof;
  st.bytes = state->bytes;
  st.carry = state->carry;

  // If we previously saw an EOF or an invalid character, bail out:
  if (st.eof) {
    *outlen = 0;
    ret = 0;
    // If there was a trailing '=' to check, check it:
    if (srclen && (st.eof == BASE64_AEOF)) {
      state->bytes = 0;
      state->eof = BASE64_EOF;
      ret = ((base64_table_dec[*c++] == 254) && (srclen == 1)) ? 1 : 0;
    }
    return ret;
  }

  // Turn four 6-bit numbers into three bytes:
  // out[0] = 11111122
  // out[1] = 22223333
  // out[2] = 33444444

  // Duff's device again:
  switch (st.bytes) {
    for (;;) {
    case 0:
// If we have native uint64's, pick off 8 bytes at a time for as long as we
// can, but make sure that we quit before seeing any == markers at the end of
// the string. Also, because we write two zeroes at the end of the output,
// ensure that there are at least 3 valid bytes of input data remaining to
// close the gap. 8 + 2 + 3 = 13 bytes:
while (srclen >= 13)
{
	uint64_t str, res, dec;

	// Load string:
	str = *(uint64_t *)c;

	// Shuffle bytes to 64-bit bigendian:
	str = cpu_to_be64(str);

	// Lookup each byte in the decoding table; if we encounter any
	// "invalid" values, fall back on the bytewise code:
	if ((dec = base64_table_dec[str >> 56]) > 63) {
		break;
	}
	res = dec << 58;

	if ((dec = base64_table_dec[(str >> 48) & 0xFF]) > 63) {
		break;
	}
	res |= dec << 52;

	if ((dec = base64_table_dec[(str >> 40) & 0xFF]) > 63) {
		break;
	}
	res |= dec << 46;

	if ((dec = base64_table_dec[(str >> 32) & 0xFF]) > 63) {
		break;
	}
	res |= dec << 40;

	if ((dec = base64_table_dec[(str >> 24) & 0xFF]) > 63) {
		break;
	}
	res |= dec << 34;

	if ((dec = base64_table_dec[(str >> 16) & 0xFF]) > 63) {
		break;
	}
	res |= dec << 28;

	if ((dec = base64_table_dec[(str >> 8) & 0xFF]) > 63) {
		break;
	}
	res |= dec << 22;

	if ((dec = base64_table_dec[str & 0xFF]) > 63) {
		break;
	}
	res |= dec << 16;

	// Reshuffle and repack into 6-byte output format:
	res = be64_to_cpu(res);

	// Store back:
	*(uint64_t *)o = res;

	c += 8;
	o += 6;
	outl += 6;
	srclen -= 8;
}

      if (srclen-- == 0) {
        ret = 1;
        break;
      }
      if ((q = base64_table_dec[*c++]) >= 254) {
        st.eof = BASE64_EOF;
        // Treat character '=' as invalid for byte 0:
        break;
      }
      st.carry = q << 2;
      st.bytes++;

    case 1:
      if (srclen-- == 0) {
        ret = 1;
        break;
      }
      if ((q = base64_table_dec[*c++]) >= 254) {
        st.eof = BASE64_EOF;
        // Treat character '=' as invalid for byte 1:
        break;
      }
      *o++ = st.carry | (q >> 4);
      st.carry = q << 4;
      st.bytes++;
      outl++;

    case 2:
      if (srclen-- == 0) {
        ret = 1;
        break;
      }
      if ((q = base64_table_dec[*c++]) >= 254) {
        st.bytes++;
        // When q == 254, the input char is '='.
        // Check if next byte is also '=':
        if (q == 254) {
          if (srclen-- != 0) {
            st.bytes = 0;
            // EOF:
            st.eof = BASE64_EOF;
            q = base64_table_dec[*c++];
            ret = ((q == 254) && (srclen == 0)) ? 1 : 0;
            break;
          } else {
            // Almost EOF
            st.eof = BASE64_AEOF;
            ret = 1;
            break;
          }
        }
        // If we get here, there was an error:
        break;
      }
      *o++ = st.carry | (q >> 2);
      st.carry = q << 6;
      st.bytes++;
      outl++;

    case 3:
      if (srclen-- == 0) {
        ret = 1;
        break;
      }
      if ((q = base64_table_dec[*c++]) >= 254) {
        st.bytes = 0;
        st.eof = BASE64_EOF;
        // When q == 254, the input char is '='. Return 1 and EOF.
        // When q == 255, the input char is invalid. Return 0 and EOF.
        ret = ((q == 254) && (srclen == 0)) ? 1 : 0;
        break;
      }
      *o++ = st.carry | q;
      st.carry = 0;
      st.bytes = 0;
      outl++;
    }
  }
  state->eof = st.eof;
  state->bytes = st.bytes;
  state->carry = st.carry;
  *outlen = outl;
  return ret;
}

static void base64_stream_encode_init(struct base64_state *state) {
  state->eof = 0;
  state->bytes = 0;
  state->carry = 0;
  //state->flags = flags; // useless
}

static void base64_stream_encode(struct base64_state *state, const char *src,
                          size_t srclen, char *out, size_t *outlen) {
  base64_stream_encode_scalar(state, src, srclen, out, outlen);
}

static void base64_stream_encode_final(struct base64_state *state, char *out,
                                size_t *outlen) {
  uint8_t *o = (uint8_t *)out;

  if (state->bytes == 1) {
    *o++ = base64_table_enc[state->carry];
    *o++ = '=';
    *o++ = '=';
    *outlen = 3;
    return;
  }
  if (state->bytes == 2) {
    *o++ = base64_table_enc[state->carry];
    *o++ = '=';
    *outlen = 2;
    return;
  }
  *outlen = 0;
}

static void base64_stream_decode_init(struct base64_state *state) {

  state->eof = 0;
  state->bytes = 0;
  state->carry = 0;
  //state->flags = flags; // useless
}

static int base64_stream_decode(struct base64_state *state, const char *src,
                         size_t srclen, char *out, size_t *outlen) {
  return base64_stream_decode_scalar(state, src, srclen, out, outlen);
}

void scalar_base64_encode(const char *src, size_t srclen, char *out, size_t *outlen) {
  size_t s;
  size_t t;
  struct base64_state state;

  // Init the stream reader:
  base64_stream_encode_init(&state);

  // Feed the whole string to the stream reader:
  base64_stream_encode(&state, src, srclen, out, &s);

  // Finalize the stream by writing trailer if any:
  base64_stream_encode_final(&state, out + s, &t);

  // Final output length is stream length plus tail:
  *outlen = s + t;
}

int scalar_base64_decode(const char *src, size_t srclen, char *out, size_t *outlen) {
  int ret;
  struct base64_state state;

  // Init the stream reader:
  base64_stream_decode_init(&state);

  // Feed the whole string to the stream reader:
  ret = base64_stream_decode(&state, src, srclen, out, outlen);

  // If when decoding a whole block, we're still waiting for input then fail:
  if (ret && (state.bytes == 0)) {
    return ret;
  }
  return 0;
}
#include <cstdint>
#include <cstring>
#include <cmath>
#include <algorithm>
#include <omp.h>

#if (defined(__x86_64__) || defined(__i386__)) && \
    (defined(__GNUC__) || defined(__clang__))
#include <immintrin.h>
#define BASE64_AVX2_TARGET __attribute__((target("avx2")))
#define BASE64_HAS_TARGETED_AVX2 1
#else
#define BASE64_HAS_TARGETED_AVX2 0
#endif

#if BASE64_HAS_TARGETED_AVX2
static inline BASE64_AVX2_TARGET bool base64_decode_avx2_block(
    const char *src, char *out) {
  const __m256i chars = _mm256_loadu_si256(
      reinterpret_cast<const __m256i *>(src));
  const __m256i upper = _mm256_and_si256(
      _mm256_cmpgt_epi8(chars, _mm256_set1_epi8('A' - 1)),
      _mm256_cmpgt_epi8(_mm256_set1_epi8('Z' + 1), chars));
  const __m256i lower = _mm256_and_si256(
      _mm256_cmpgt_epi8(chars, _mm256_set1_epi8('a' - 1)),
      _mm256_cmpgt_epi8(_mm256_set1_epi8('z' + 1), chars));
  const __m256i digit = _mm256_and_si256(
      _mm256_cmpgt_epi8(chars, _mm256_set1_epi8('0' - 1)),
      _mm256_cmpgt_epi8(_mm256_set1_epi8('9' + 1), chars));
  const __m256i plus = _mm256_cmpeq_epi8(chars, _mm256_set1_epi8('+'));
  const __m256i slash = _mm256_cmpeq_epi8(chars, _mm256_set1_epi8('/'));
  const __m256i valid = _mm256_or_si256(
      _mm256_or_si256(upper, lower),
      _mm256_or_si256(digit, _mm256_or_si256(plus, slash)));

  if (_mm256_movemask_epi8(valid) != -1) {
    return false;
  }

  __m256i sextets = _mm256_sub_epi8(chars, _mm256_set1_epi8('A'));
  const __m256i lower_values = _mm256_add_epi8(
      _mm256_sub_epi8(chars, _mm256_set1_epi8('a')),
      _mm256_set1_epi8(26));
  const __m256i digit_values = _mm256_add_epi8(
      _mm256_sub_epi8(chars, _mm256_set1_epi8('0')),
      _mm256_set1_epi8(52));
  sextets = _mm256_blendv_epi8(sextets, lower_values, lower);
  sextets = _mm256_blendv_epi8(sextets, digit_values, digit);
  sextets = _mm256_blendv_epi8(sextets, _mm256_set1_epi8(62), plus);
  sextets = _mm256_blendv_epi8(sextets, _mm256_set1_epi8(63), slash);

  // Pair adjacent sextets, then combine each pair into a 24-bit output word.
  const __m256i pairs = _mm256_maddubs_epi16(
      sextets, _mm256_set1_epi16(0x0140));
  const __m256i words = _mm256_madd_epi16(
      pairs, _mm256_set1_epi32(0x00011000));
  const __m256i shuffle = _mm256_setr_epi8(
      2, 1, 0, 6, 5, 4, 10, 9, 8, 14, 13, 12, -128, -128, -128, -128,
      2, 1, 0, 6, 5, 4, 10, 9, 8, 14, 13, 12, -128, -128, -128, -128);
  const __m256i packed = _mm256_shuffle_epi8(words, shuffle);

  // Each 128-bit lane holds 12 useful bytes; copy only those bytes.
  uint8_t packed_bytes[32];
  _mm256_storeu_si256(reinterpret_cast<__m256i *>(packed_bytes), packed);
  std::memcpy(out, packed_bytes, 12);
  std::memcpy(out + 12, packed_bytes + 16, 12);
  return true;
}

static BASE64_AVX2_TARGET bool base64_decode_avx2_prefix(
    const char *src, size_t vector_chars, char *out, size_t *decoded_len) {
  size_t in_offset = 0;
  size_t out_offset = 0;

  // Unroll by two blocks while keeping a bounded single-block remainder.
  for (; vector_chars - in_offset >= 64; in_offset += 64, out_offset += 48) {
    if (!base64_decode_avx2_block(src + in_offset, out + out_offset) ||
        !base64_decode_avx2_block(src + in_offset + 32, out + out_offset + 24)) {
      return false;
    }
  }
  for (; in_offset < vector_chars; in_offset += 32, out_offset += 24) {
    if (!base64_decode_avx2_block(src + in_offset, out + out_offset)) {
      return false;
    }
  }

  *decoded_len = out_offset;
  return true;
}
#endif

static bool base64_avx2_supported() {
#if BASE64_HAS_TARGETED_AVX2
  static const bool supported = __builtin_cpu_supports("avx2") != 0;
  return supported;
#else
  return false;
#endif
}

static int base64_decode_dispatch(const char *src, size_t srclen,
                                 char *out, size_t *outlen) {
#if BASE64_HAS_TARGETED_AVX2
  if (srclen >= 32 && base64_avx2_supported()) {
    size_t vector_limit = srclen;
    // Keep the final quartet on the scalar path when padding is present.
    if (src[srclen - 1] == '=') {
      vector_limit = (srclen >= 4) ? srclen - 4 : 0;
    }
    const size_t vector_chars = vector_limit & ~static_cast<size_t>(31);
    if (vector_chars != 0) {
      size_t vector_len = 0;
      if (base64_decode_avx2_prefix(src, vector_chars, out, &vector_len)) {
        size_t tail_len = 0;
        const int ok = scalar_base64_decode(
            src + vector_chars, srclen - vector_chars,
            out + vector_len, &tail_len);
        *outlen = vector_len + tail_len;
        return ok;
      }
      // An invalid SIMD block may follow already-written blocks. Recompute the
      // complete input with the scalar decoder to preserve its error behavior.
    }
  }
#endif
  return scalar_base64_decode(src, srclen, out, outlen);
}

extern "C" void run(const void *input1, const void *input2, void *output,
                    int n, int parameter, int threads) {
  size_t len = 0;
  int ok = base64_decode_dispatch((const char *)input1, n,
                                  ((char *)output) + 16, &len);
  *(uint64_t *)output = ok ? len : UINT64_MAX;
}
