#include <stddef.h>
#include <stdint.h>

static const uint8_t base64_table_enc[] = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";

static const uint8_t base64_table_dec[128] = {
    255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255,
    255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255,
    255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 62, 255, 255, 255, 63,
    52, 53, 54, 55, 56, 57, 58, 59, 60, 61, 255, 255, 255, 254, 255, 255,
    255, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14,
    15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 255, 255, 255, 255, 255,
    255, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40,
    41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51, 255, 255, 255, 255, 255
};

static inline uint8_t base64_value(unsigned char c) {
    return c < 128 ? base64_table_dec[c] : 255;
}

extern "C" void scalar_base64_encode(const char *src, size_t srclen, char *out, size_t *outlen) {
    const uint8_t *s = reinterpret_cast<const uint8_t *>(src);
    uint8_t *o = reinterpret_cast<uint8_t *>(out);
    while (srclen >= 3) {
        const uint32_t v = (static_cast<uint32_t>(s[0]) << 16) |
                           (static_cast<uint32_t>(s[1]) << 8) |
                           static_cast<uint32_t>(s[2]);
        *o++ = base64_table_enc[(v >> 18) & 63];
        *o++ = base64_table_enc[(v >> 12) & 63];
        *o++ = base64_table_enc[(v >> 6) & 63];
        *o++ = base64_table_enc[v & 63];
        s += 3;
        srclen -= 3;
    }
    if (srclen == 1) {
        const uint8_t a = s[0];
        *o++ = base64_table_enc[a >> 2];
        *o++ = base64_table_enc[(a & 3) << 4];
        *o++ = '=';
        *o++ = '=';
    } else if (srclen == 2) {
        const uint8_t a = s[0];
        const uint8_t b = s[1];
        *o++ = base64_table_enc[a >> 2];
        *o++ = base64_table_enc[((a & 3) << 4) | (b >> 4)];
        *o++ = base64_table_enc[(b & 15) << 2];
        *o++ = '=';
    }
    *outlen = static_cast<size_t>(o - reinterpret_cast<uint8_t *>(out));
}

extern "C" int scalar_base64_decode(const char *src, size_t srclen, char *out, size_t *outlen) {
    const unsigned char *s = reinterpret_cast<const unsigned char *>(src);
    uint8_t *dst = reinterpret_cast<uint8_t *>(out);
    size_t i = 0;

    // Decode two independent eight-character groups per iteration. Leave at
    // least one quartet for the scalar tail so padding is never bulk-decoded.
    while (srclen - i >= 20) {
        const uint8_t a0 = base64_value(s[i]);
        const uint8_t a1 = base64_value(s[i + 8]);
        const uint8_t b0 = base64_value(s[i + 1]);
        const uint8_t b1 = base64_value(s[i + 9]);
        const uint8_t c0 = base64_value(s[i + 2]);
        const uint8_t c1 = base64_value(s[i + 10]);
        const uint8_t d0 = base64_value(s[i + 3]);
        const uint8_t d1 = base64_value(s[i + 11]);
        const uint8_t e0 = base64_value(s[i + 4]);
        const uint8_t e1 = base64_value(s[i + 12]);
        const uint8_t f0 = base64_value(s[i + 5]);
        const uint8_t f1 = base64_value(s[i + 13]);
        const uint8_t g0 = base64_value(s[i + 6]);
        const uint8_t g1 = base64_value(s[i + 14]);
        const uint8_t h0 = base64_value(s[i + 7]);
        const uint8_t h1 = base64_value(s[i + 15]);

        if ((a0 | b0 | c0 | d0 | e0 | f0 | g0 | h0) > 63 ||
            (a1 | b1 | c1 | d1 | e1 | f1 | g1 | h1) > 63) {
            break;
        }

        dst[0] = static_cast<uint8_t>((a0 << 2) | (b0 >> 4));
        dst[1] = static_cast<uint8_t>((b0 << 4) | (c0 >> 2));
        dst[2] = static_cast<uint8_t>((c0 << 6) | d0);
        dst[3] = static_cast<uint8_t>((e0 << 2) | (f0 >> 4));
        dst[4] = static_cast<uint8_t>((f0 << 4) | (g0 >> 2));
        dst[5] = static_cast<uint8_t>((g0 << 6) | h0);
        dst[6] = static_cast<uint8_t>((a1 << 2) | (b1 >> 4));
        dst[7] = static_cast<uint8_t>((b1 << 4) | (c1 >> 2));
        dst[8] = static_cast<uint8_t>((c1 << 6) | d1);
        dst[9] = static_cast<uint8_t>((e1 << 2) | (f1 >> 4));
        dst[10] = static_cast<uint8_t>((f1 << 4) | (g1 >> 2));
        dst[11] = static_cast<uint8_t>((g1 << 6) | h1);
        dst += 12;
        i += 16;
    }

    while (i < srclen) {
        if (srclen - i < 4) {
            *outlen = static_cast<size_t>(dst - reinterpret_cast<uint8_t *>(out));
            return 0;
        }
        const uint8_t a = base64_value(s[i]);
        const uint8_t b = base64_value(s[i + 1]);
        const uint8_t c = base64_value(s[i + 2]);
        const uint8_t d = base64_value(s[i + 3]);
        if (a > 63 || b > 63) {
            *outlen = static_cast<size_t>(dst - reinterpret_cast<uint8_t *>(out));
            return 0;
        }
        dst[0] = static_cast<uint8_t>((a << 2) | (b >> 4));
        if (c == 254) {
            if (d != 254 || srclen - i != 4) {
                *outlen = static_cast<size_t>(dst - reinterpret_cast<uint8_t *>(out));
                return 0;
            }
            ++dst;
            i += 4;
            continue;
        }
        if (c > 63) {
            *outlen = static_cast<size_t>(dst - reinterpret_cast<uint8_t *>(out));
            return 0;
        }
        dst[1] = static_cast<uint8_t>((b << 4) | (c >> 2));
        if (d == 254) {
            if (srclen - i != 4) {
                *outlen = static_cast<size_t>(dst - reinterpret_cast<uint8_t *>(out));
                return 0;
            }
            dst += 2;
            i += 4;
            continue;
        }
        if (d > 63) {
            *outlen = static_cast<size_t>(dst - reinterpret_cast<uint8_t *>(out));
            return 0;
        }
        dst[2] = static_cast<uint8_t>((c << 6) | d);
        dst += 3;
        i += 4;
    }

    *outlen = static_cast<size_t>(dst - reinterpret_cast<uint8_t *>(out));
    return 1;
}

extern "C" void run(const void *input1, const void *input2, void *output, int n, int parameter, int threads) {
    (void)input2;
    (void)parameter;
    (void)threads;
    size_t len = 0;
    const int ok = n >= 0 && scalar_base64_decode(static_cast<const char *>(input1),
                                                  static_cast<size_t>(n),
                                                  static_cast<char *>(output) + 16,
                                                  &len);
    *static_cast<uint64_t *>(output) = ok ? static_cast<uint64_t>(len) : static_cast<uint64_t>(-1);
}
