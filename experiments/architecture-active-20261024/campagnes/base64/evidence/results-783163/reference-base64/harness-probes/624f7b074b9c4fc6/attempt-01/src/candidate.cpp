#ifndef SCALAR_B64
#define SCALAR_B64

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

int scalar_base64_decode(const char *src, size_t srclen, char *out, size_t *outlen);
void scalar_base64_encode(const char *src, size_t srclen, char *out, size_t *outlen);

#ifdef __cplusplus
}
#endif

#endif

static const uint8_t base64_table_enc[] =
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";

static const uint8_t base64_table_dec[] = {
    255,255,255,255,255,255,255,255,255,255,255,255,255,255,255,255,
    255,255,255,255,255,255,255,255,255,255,255,255,255,255,255,255,
    255,255,255,255,255,255,255,255,255,255,255,62,255,255,255,63,
    52,53,54,55,56,57,58,59,60,61,255,255,255,254,255,255,
    255,0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,
    15,16,17,18,19,20,21,22,23,24,25,255,255,255,255,255,
    255,26,27,28,29,30,31,32,33,34,35,36,37,38,39,40,
    41,42,43,44,45,46,47,48,49,50,51,255,255,255,255,255,
    255,255,255,255,255,255,255,255,255,255,255,255,255,255,255,255,
    255,255,255,255,255,255,255,255,255,255,255,255,255,255,255,255,
    255,255,255,255,255,255,255,255,255,255,255,255,255,255,255,255,
    255,255,255,255,255,255,255,255,255,255,255,255,255,255,255,255,
    255,255,255,255,255,255,255,255,255,255,255,255,255,255,255,255,
    255,255,255,255,255,255,255,255,255,255,255,255,255,255,255,255,
    255,255,255,255,255,255,255,255,255,255,255,255,255,255,255,255,
    255,255,255,255,255,255,255,255,255,255,255,255,255,255,255,255
};

struct base64_state {
    int eof;
    int bytes;
    unsigned char carry;
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

#define BASE64_AEOF 1
#define BASE64_EOF 2

void base64_stream_encode_scalar(struct base64_state *state, const char *src,
                                 size_t srclen, char *out, size_t *outlen) {
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

static inline int base64_decode8_scalar(uint64_t str, uint64_t *result) {
    const uint64_t d0 = base64_table_dec[str >> 56];
    const uint64_t d1 = base64_table_dec[(str >> 48) & 0xFF];
    const uint64_t d2 = base64_table_dec[(str >> 40) & 0xFF];
    const uint64_t d3 = base64_table_dec[(str >> 32) & 0xFF];
    const uint64_t d4 = base64_table_dec[(str >> 24) & 0xFF];
    const uint64_t d5 = base64_table_dec[(str >> 16) & 0xFF];
    const uint64_t d6 = base64_table_dec[(str >> 8) & 0xFF];
    const uint64_t d7 = base64_table_dec[str & 0xFF];

    if ((d0 | d1 | d2 | d3 | d4 | d5 | d6 | d7) > 63) return 0;

    uint64_t res = (d0 << 58) | (d1 << 52) | (d2 << 46) | (d3 << 40) |
                   (d4 << 34) | (d5 << 28) | (d6 << 22) | (d7 << 16);
    *result = be64_to_cpu(res);
    return 1;
}

int base64_stream_decode_scalar(struct base64_state *state, const char *src,
                                size_t srclen, char *out, size_t *outlen) {
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
            while (srclen >= 37) {
                uint64_t str0 = cpu_to_be64(*(uint64_t *)(c + 0));
                uint64_t str1 = cpu_to_be64(*(uint64_t *)(c + 8));
                uint64_t str2 = cpu_to_be64(*(uint64_t *)(c + 16));
                uint64_t str3 = cpu_to_be64(*(uint64_t *)(c + 24));
                uint64_t res0, res1, res2, res3;
                int valid0 = base64_decode8_scalar(str0, &res0);
                int valid1 = base64_decode8_scalar(str1, &res1);
                int valid2 = base64_decode8_scalar(str2, &res2);
                int valid3 = base64_decode8_scalar(str3, &res3);

                if (!valid0 || !valid1 || !valid2 || !valid3) break;

                *(uint64_t *)o = res0;
                *(uint64_t *)(o + 6) = res1;
                *(uint64_t *)(o + 12) = res2;
                *(uint64_t *)(o + 18) = res3;
                c += 32;
                o += 24;
                outl += 24;
                srclen -= 32;
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
}

static int base64_stream_decode(struct base64_state *state, const char *src,
                                size_t srclen, char *out, size_t *outlen) {
    return base64_stream_decode_scalar(state, src, srclen, out, outlen);
}

void scalar_base64_encode(const char *src, size_t srclen, char *out,
                          size_t *outlen) {
    size_t s, t;
    struct base64_state state;
    base64_stream_encode_init(&state);
    base64_stream_encode(&state, src, srclen, out, &s);
    base64_stream_encode_final(&state, out + s, &t);
    *outlen = s + t;
}

int scalar_base64_decode(const char *src, size_t srclen, char *out,
                         size_t *outlen) {
    int ret;
    struct base64_state state;
    base64_stream_decode_init(&state);
    ret = base64_stream_decode(&state, src, srclen, out, outlen);
    if (ret && (state.bytes == 0)) return ret;
    return 0;
}

#include <cstdint>
#include <cstring>
#include <cmath>
#include <algorithm>
#include <omp.h>
extern "C" void run(const void *input1, const void *input2, void *output,
                    int n, int parameter, int threads) {
    size_t len = 0;
    int ok = scalar_base64_decode((const char *)input1, n,
                                  ((char *)output) + 16, &len);
    *(uint64_t *)output = ok ? len : UINT64_MAX;
}
