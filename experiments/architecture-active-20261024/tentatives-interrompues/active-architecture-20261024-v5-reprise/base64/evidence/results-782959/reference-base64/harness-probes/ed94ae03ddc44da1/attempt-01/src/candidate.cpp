#ifndef SCALAR_B64
#define SCALAR_B64
#include <stddef.h>
#include <stdint.h>
#include <string.h>
#ifdef __cplusplus
extern "C" {
#endif
int scalar_base64_decode(const char *src, size_t srclen, char *out, size_t *outlen);
void scalar_base64_encode(const char *src, size_t srclen, char *out, size_t *outlen);
#ifdef __cplusplus
}
#endif
#endif

static const uint8_t base64_table_enc[] = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
                                   "abcdefghijklmnopqrstuvwxyz"
                                   "0123456789+/";

static const uint8_t base64_table_dec[] = {
    255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255,
    255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255,
    255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 62, 255, 255, 255, 63,
    52, 53, 54, 55, 56, 57, 58, 59, 60, 61, 255, 255, 255, 254, 255, 255,
    255, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14,
    15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 255, 255, 255, 255, 255,
    255, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40,
    41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51, 255, 255, 255, 255, 255,
    255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255,
    255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255,
    255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255,
    255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255,
    255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255,
    255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255,
    255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255,
    255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255
};

struct base64_state {
    int eof;
    int bytes;
    unsigned char carry;
};

#define UNUSED(x) ((void)(x))
#define BASE64_ENC_STUB \
  UNUSED(state); \
  UNUSED(src); \
  UNUSED(srclen); \
  UNUSED(out); \
  *outlen = 0;
#define BASE64_DEC_STUB \
  UNUSED(state); \
  UNUSED(src); \
  UNUSED(srclen); \
  UNUSED(out); \
  UNUSED(outlen); \
  return -1;

struct codec {
    void (*enc)(struct base64_state *state, const char *src, size_t srclen, char *out, size_t *outlen);
    int (*dec)(struct base64_state *state, const char *src, size_t srclen, char *out, size_t *outlen);
};

#if (__BYTE_ORDER__ == __ORDER_LITTLE_ENDIAN__)
#define BASE64_LITTLE_ENDIAN 1
#else
#define BASE64_LITTLE_ENDIAN 0
#endif
#ifdef __LITTLE_ENDIAN__
#define BASE64_LITTLE_ENDIAN 1
#endif
#ifdef __BIG_ENDIAN__
#define BASE64_LITTLE_ENDIAN 0
#endif
#if BASE64_LITTLE_ENDIAN
#if defined(_MSC_VER)
#define cpu_to_be32(x) _byteswap_ulong(x)
#define cpu_to_be64(x) _byteswap_uint64(x)
#define be32_to_cpu(x) _byteswap_ulong(x)
#define be64_to_cpu(x) _byteswap_uint64(x)
#else
#define cpu_to_be32(x) __builtin_bswap32(x)
#define cpu_to_be64(x) __builtin_bswap64(x)
#define be32_to_cpu(x) __builtin_bswap32(x)
#define be64_to_cpu(x) __builtin_bswap64(x)
#endif
#else
#define cpu_to_be32(x) (x)
#define cpu_to_be64(x) (x)
#define be32_to_cpu(x) (x)
#define be64_to_cpu(x) (x)
#endif
#ifdef _INTEGRAL_MAX_BITS
#define BASE64_WORDSIZE _INTEGRAL_MAX_BITS
#else
#define BASE64_WORDSIZE __WORDSIZE
#endif
#define BASE64_AEOF 1
#define BASE64_EOF 2

void base64_stream_encode_scalar(struct base64_state *state, const char *src, size_t srclen, char *out, size_t *outlen) {
    const uint8_t *c = (const uint8_t *)src;
    uint8_t *o = (uint8_t *)out;
    size_t outl = 0;
    struct base64_state st;
    st.bytes = state->bytes;
    st.carry = state->carry;
    switch (st.bytes) {
        for (;;) {
        case 0:
            while (srclen >= 8) {
                uint64_t str = *(uint64_t *)c;
                str = cpu_to_be64(str);
                *o++ = base64_table_enc[(str >> 58) & 0x3F];
                *o++ = base64_table_enc[(str >> 52) & 0x3F];
                *o++ = base64_table_enc[(str >> 46) & 0x3F];
                *o++ = base64_table_enc[(str >> 40) & 0x3F];
                *o++ = base64_table_enc[(str >> 34) & 0x3F];
                *o++ = base64_table_enc[(str >> 28) & 0x3F];
                *o++ = base64_table_enc[(str >> 22) & 0x3F];
                *o++ = base64_table_enc[(str >> 16) & 0x3F];
                c += 6;
                outl += 8;
                srclen -= 6;
            }
            if (srclen-- == 0) break;
            *o++ = base64_table_enc[*c >> 2];
            st.carry = (*c++ << 4) & 0x30;
            st.bytes++;
            outl++;
        case 1:
            if (srclen-- == 0) break;
            *o++ = base64_table_enc[st.carry | (*c >> 4)];
            st.carry = (*c++ << 2) & 0x3C;
            st.bytes++;
            outl++;
        case 2:
            if (srclen-- == 0) break;
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

static inline uint64_t base64_repeat16(uint16_t value) {
    return 0x0001000100010001ULL * value;
}

static inline uint64_t base64_swar_ge16(uint64_t lanes, uint16_t threshold) {
    const uint64_t high_bits = 0x8000800080008000ULL;
    const uint64_t ge_bits = ((lanes | high_bits) - base64_repeat16(threshold)) & high_bits;
    return (ge_bits >> 15) * 0x0000FFFFULL;
}

static inline uint64_t base64_swar_range16(uint64_t lanes, uint16_t low, uint16_t high_exclusive) {
    const uint64_t lane_mask = 0xFFFFFFFFFFFFFFFFULL;
    return base64_swar_ge16(lanes, low) & ~base64_swar_ge16(lanes, high_exclusive) & lane_mask;
}

static inline uint64_t base64_swar_eq16(uint64_t lanes, uint16_t value) {
    const uint64_t high_bits = 0x8000800080008000ULL;
    const uint64_t diff = lanes ^ base64_repeat16(value);
    const uint64_t nonzero_bits = ((diff | high_bits) - base64_repeat16(1)) & high_bits;
    const uint64_t nonzero_mask = (nonzero_bits >> 15) * 0x0000FFFFULL;
    return ~nonzero_mask;
}

static inline int base64_swar_decode4_word(uint32_t raw, uint32_t *packed_out) {
    const uint64_t lane_mask = 0xFFFFFFFFFFFFFFFFULL;
    const uint64_t low_byte_mask = 0x00FF00FF00FF00FFULL;
    const uint64_t low5_mask = 0x001F001F001F001FULL;
    const uint64_t repeat4 = base64_repeat16(4);
    const uint64_t repeat32 = base64_repeat16(0x20);
    uint64_t lanes = (uint64_t)((raw >> 24) & 0xFF)
                   | ((uint64_t)((raw >> 16) & 0xFF) << 16)
                   | ((uint64_t)((raw >> 8) & 0xFF) << 32)
                   | ((uint64_t)(raw & 0xFF) << 48);
    const uint64_t folded = lanes & 0x00DF00DF00DF00DFULL;
    const uint64_t letters_mask = base64_swar_range16(folded, 65, 91);
    const uint64_t digits_mask = base64_swar_range16(lanes, 48, 58);
    const uint64_t punctuation_mask = base64_swar_eq16(lanes & 0x00FB00FB00FB00FBULL, 43);
    if ((letters_mask | digits_mask | punctuation_mask) != lane_mask) return 0;
    const uint64_t low5 = lanes & low5_mask;
    const uint64_t letter_base = (low5 + base64_repeat16(255)) & low_byte_mask;
    const uint64_t lower_bit = lanes & repeat32;
    const uint64_t case_adjust = (lower_bit >> 1) + (lower_bit >> 2) + (lower_bit >> 4);
    const uint64_t letters = (letter_base + case_adjust) & letters_mask;
    const uint64_t digits = (lanes + repeat4) & digits_mask;
    const uint64_t punctuation = (base64_repeat16(62) + ((lanes & repeat4) >> 2)) & punctuation_mask;
    const uint64_t sextets = letters | digits | punctuation;
    const uint32_t q0 = (uint32_t)(sextets & 0x3F);
    const uint32_t q1 = (uint32_t)((sextets >> 16) & 0x3F);
    const uint32_t q2 = (uint32_t)((sextets >> 32) & 0x3F);
    const uint32_t q3 = (uint32_t)((sextets >> 48) & 0x3F);
    *packed_out = (q0 << 18) | (q1 << 12) | (q2 << 6) | q3;
    return 1;
}

int base64_stream_decode_scalar(struct base64_state *state, const char *src, size_t srclen, char *out, size_t *outlen) {
    int ret = 0;
    const uint8_t *c = (const uint8_t *)src;
    uint8_t *o = (uint8_t *)out;
    uint8_t q;
    size_t outl = 0;
    struct base64_state st;
    st.eof = state->eof;
    st.bytes = state->bytes;
    st.carry = state->carry;
    if (st.eof) {
        *outlen = 0;
        ret = 0;
        if (srclen && (st.eof == BASE64_AEOF)) {
            state->bytes = 0;
            state->eof = BASE64_EOF;
            ret = ((base64_table_dec[*c++] == 254) && (srclen == 1)) ? 1 : 0;
        }
        return ret;
    }
    switch (st.bytes) {
        for (;;) {
        case 0:
            while (srclen >= 13) {
                uint64_t str;
                uint32_t first, second;
                memcpy(&str, c, sizeof str);
                str = cpu_to_be64(str);
                if (!base64_swar_decode4_word((uint32_t)(str >> 32), &first) ||
                    !base64_swar_decode4_word((uint32_t)str, &second)) {
                    break;
                }
                o[0] = (uint8_t)(first >> 16);
                o[1] = (uint8_t)(first >> 8);
                o[2] = (uint8_t)first;
                o[3] = (uint8_t)(second >> 16);
                o[4] = (uint8_t)(second >> 8);
                o[5] = (uint8_t)second;
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
                if (q == 254) {
                    if (srclen-- != 0) {
                        st.bytes = 0;
                        st.eof = BASE64_EOF;
                        q = base64_table_dec[*c++];
                        ret = ((q == 254) && (srclen == 0)) ? 1 : 0;
                        break;
                    } else {
                        st.eof = BASE64_AEOF;
                        ret = 1;
                        break;
                    }
                }
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
}

static void base64_stream_encode(struct base64_state *state, const char *src, size_t srclen, char *out, size_t *outlen) {
    base64_stream_encode_scalar(state, src, srclen, out, outlen);
}

static void base64_stream_encode_final(struct base64_state *state, char *out, size_t *outlen) {
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
}

static int base64_stream_decode(struct base64_state *state, const char *src, size_t srclen, char *out, size_t *outlen) {
    return base64_stream_decode_scalar(state, src, srclen, out, outlen);
}

void scalar_base64_encode(const char *src, size_t srclen, char *out, size_t *outlen) {
    size_t s;
    size_t t;
    struct base64_state state;
    base64_stream_encode_init(&state);
    base64_stream_encode(&state, src, srclen, out, &s);
    base64_stream_encode_final(&state, out + s, &t);
    *outlen = s + t;
}

int scalar_base64_decode(const char *src, size_t srclen, char *out, size_t *outlen) {
    struct base64_state state;
    base64_stream_decode_init(&state);
    int ret = base64_stream_decode(&state, src, srclen, out, outlen);
    if (ret && (state.bytes == 0)) return ret;
    return 0;
}

#include <cstdint>
#include <cstring>
#include <cmath>
#include <algorithm>
#include <omp.h>
extern "C" void run(const void *input1, const void *input2, void *output, int n, int parameter, int threads) {
    size_t len = 0;
    int ok = scalar_base64_decode((const char *)input1, n, ((char *)output) + 16, &len);
    *(uint64_t *)output = ok ? len : UINT64_MAX;
}
