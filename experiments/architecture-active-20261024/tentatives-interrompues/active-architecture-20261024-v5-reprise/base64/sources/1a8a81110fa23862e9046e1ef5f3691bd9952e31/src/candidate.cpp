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

#include <omp.h>

static const uint8_t base64_table_enc[] = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
                                         "abcdefghijklmnopqrstuvwxyz"
                                         "0123456789+/";

static inline uint64_t base64_to_be64(uint64_t value) {
#if defined(__BYTE_ORDER__) && defined(__ORDER_LITTLE_ENDIAN__) && __BYTE_ORDER__ == __ORDER_LITTLE_ENDIAN__
    return __builtin_bswap64(value);
#else
    return value;
#endif
}

static inline uint8_t base64_decode_value(uint8_t c) {
    if (c >= (uint8_t)'A' && c <= (uint8_t)'Z') return (uint8_t)(c - (uint8_t)'A');
    if (c >= (uint8_t)'a' && c <= (uint8_t)'z') return (uint8_t)(c - (uint8_t)'a' + 26);
    if (c >= (uint8_t)'0' && c <= (uint8_t)'9') return (uint8_t)(c - (uint8_t)'0' + 52);
    if (c == (uint8_t)'+') return 62;
    if (c == (uint8_t)'/') return 63;
    if (c == (uint8_t)'=') return 254;
    return 255;
}

static inline uint32_t base64_repeat8(uint8_t value) {
    return 0x01010101u * (uint32_t)value;
}

static inline uint32_t base64_swar_ge8(uint32_t bytes, uint8_t threshold) {
    const uint32_t high_bits = 0x80808080u;
    return ((bytes | high_bits) - base64_repeat8(threshold)) & high_bits;
}

static inline uint32_t base64_swar_eq8(uint32_t bytes, uint8_t value) {
    const uint32_t high_bits = 0x80808080u;
    const uint32_t diff = bytes ^ base64_repeat8(value);
    const uint32_t nonzero = ((diff | high_bits) - base64_repeat8(1)) & high_bits;
    return high_bits & ~nonzero;
}

static inline uint32_t base64_swar_expand8(uint32_t flags) {
    return (flags >> 7) * 0xFFu;
}

static inline int base64_swar_decode4_word(uint32_t raw, uint32_t *packed_out) {
    const uint32_t high_bits = 0x80808080u;
    const uint32_t one_per_byte = 0x01010101u;
    const uint32_t ascii_flags = (~raw) & high_bits;
    const uint32_t letters_flags = base64_swar_ge8(raw, 65) & ~base64_swar_ge8(raw, 91) & ascii_flags;
    const uint32_t digits_flags = base64_swar_ge8(raw, 48) & ~base64_swar_ge8(raw, 58) & ascii_flags;
    const uint32_t punctuation_flags = base64_swar_eq8(raw, 43) | base64_swar_eq8(raw, 47);
    if ((letters_flags | digits_flags | punctuation_flags) != high_bits) return 0;

    const uint32_t letters_mask = base64_swar_expand8(letters_flags);
    const uint32_t digits_mask = base64_swar_expand8(digits_flags);
    const uint32_t punctuation_mask = base64_swar_expand8(punctuation_flags);
    const uint32_t safe_low5 = (raw & 0x1F1F1F1Fu) | (~letters_mask & one_per_byte);
    const uint32_t letter_base = safe_low5 - one_per_byte;
    const uint32_t lowercase_bits = raw & 0x20202020u & letters_mask;
    const uint32_t case_adjust = (lowercase_bits >> 1) + (lowercase_bits >> 2) + (lowercase_bits >> 4);
    const uint32_t letters = (letter_base + case_adjust) & letters_mask;
    const uint32_t digits = ((raw & 0x3F3F3F3Fu) + (digits_mask & 0x04040404u)) & digits_mask;
    const uint32_t punctuation = (0x3E3E3E3Eu + ((raw & 0x04040404u) >> 2)) & punctuation_mask;
    const uint32_t sextets = letters | digits | punctuation;

    const uint32_t q0 = (sextets >> 24) & 0x3Fu;
    const uint32_t q1 = (sextets >> 16) & 0x3Fu;
    const uint32_t q2 = (sextets >> 8) & 0x3Fu;
    const uint32_t q3 = sextets & 0x3Fu;
    *packed_out = (q0 << 18) | (q1 << 12) | (q2 << 6) | q3;
    return 1;
}

void scalar_base64_encode(const char *src, size_t srclen, char *out, size_t *outlen) {
    const uint8_t *input = (const uint8_t *)src;
    size_t i = 0;
    size_t written = 0;
    while (srclen - i >= 3) {
        const uint32_t value = ((uint32_t)input[i] << 16) | ((uint32_t)input[i + 1] << 8) | input[i + 2];
        out[written++] = (char)base64_table_enc[(value >> 18) & 0x3Fu];
        out[written++] = (char)base64_table_enc[(value >> 12) & 0x3Fu];
        out[written++] = (char)base64_table_enc[(value >> 6) & 0x3Fu];
        out[written++] = (char)base64_table_enc[value & 0x3Fu];
        i += 3;
    }
    if (srclen - i == 1) {
        const uint32_t value = (uint32_t)input[i] << 16;
        out[written++] = (char)base64_table_enc[(value >> 18) & 0x3Fu];
        out[written++] = (char)base64_table_enc[(value >> 12) & 0x3Fu];
        out[written++] = '=';
        out[written++] = '=';
    } else if (srclen - i == 2) {
        const uint32_t value = ((uint32_t)input[i] << 16) | ((uint32_t)input[i + 1] << 8);
        out[written++] = (char)base64_table_enc[(value >> 18) & 0x3Fu];
        out[written++] = (char)base64_table_enc[(value >> 12) & 0x3Fu];
        out[written++] = (char)base64_table_enc[(value >> 6) & 0x3Fu];
        out[written++] = '=';
    }
    *outlen = written;
}

int scalar_base64_decode(const char *src, size_t srclen, char *out, size_t *outlen) {
    const uint8_t *input = (const uint8_t *)src;
    uint8_t *output = (uint8_t *)out;
    size_t pos = 0;
    size_t written = 0;
    if (srclen == 0) {
        *outlen = 0;
        return 1;
    }
    if ((srclen & 3u) != 0) {
        *outlen = 0;
        return 0;
    }

    size_t data_end = srclen;
    if (input[srclen - 1] == (uint8_t)'=') {
        --data_end;
        if (data_end > 0 && input[data_end - 1] == (uint8_t)'=') --data_end;
    }

    while (data_end - pos >= 8) {
        uint64_t block;
        uint32_t first;
        uint32_t second;
        memcpy(&block, input + pos, sizeof block);
        block = base64_to_be64(block);
        first = (uint32_t)(block >> 32);
        second = (uint32_t)block;
        uint32_t first_packed;
        uint32_t second_packed;
        if (!base64_swar_decode4_word(first, &first_packed) ||
            !base64_swar_decode4_word(second, &second_packed)) {
            break;
        }
        output[written++] = (uint8_t)(first_packed >> 16);
        output[written++] = (uint8_t)(first_packed >> 8);
        output[written++] = (uint8_t)first_packed;
        output[written++] = (uint8_t)(second_packed >> 16);
        output[written++] = (uint8_t)(second_packed >> 8);
        output[written++] = (uint8_t)second_packed;
        pos += 8;
    }

    while (pos < srclen) {
        const int last_group = (srclen - pos == 4);
        const uint8_t q0 = base64_decode_value(input[pos]);
        const uint8_t q1 = base64_decode_value(input[pos + 1]);
        const uint8_t q2 = base64_decode_value(input[pos + 2]);
        const uint8_t q3 = base64_decode_value(input[pos + 3]);
        if (q0 > 63 || q1 > 63) {
            *outlen = written;
            return 0;
        }
        output[written++] = (uint8_t)((q0 << 2) | (q1 >> 4));
        if (q2 == 254) {
            if (!last_group || q3 != 254) {
                *outlen = written;
                return 0;
            }
            *outlen = written;
            return 1;
        }
        if (q2 > 63) {
            *outlen = written;
            return 0;
        }
        output[written++] = (uint8_t)((q1 << 4) | (q2 >> 2));
        if (q3 == 254) {
            if (!last_group) {
                *outlen = written;
                return 0;
            }
            *outlen = written;
            return 1;
        }
        if (q3 > 63) {
            *outlen = written;
            return 0;
        }
        output[written++] = (uint8_t)((q2 << 6) | q3);
        pos += 4;
    }
    *outlen = written;
    return 1;
}

extern "C" void run(const void *input1, const void *input2, void *output, int n, int parameter, int threads) {
    (void)input2;
    (void)parameter;
    (void)threads;
    size_t len = 0;
    int ok = scalar_base64_decode((const char *)input1, (size_t)n, ((char *)output) + 16, &len);
    *(uint64_t *)output = ok ? len : UINT64_MAX;
}
