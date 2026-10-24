#include <cstddef>
#include <cstdint>
#include <cstring>
#include <immintrin.h>

static inline unsigned int b64_value(unsigned char c) {
    if (c >= 'A' && c <= 'Z') return c - 'A';
    if (c >= 'a' && c <= 'z') return c - 'a' + 26;
    if (c >= '0' && c <= '9') return c - '0' + 52;
    if (c == '+') return 62;
    return 63; // '/' for valid standard Base64 input
}

__attribute__((target("avx2")))
static void decode_avx2_blocks(const unsigned char* src,
                               unsigned char* dst,
                               std::size_t chars) {
    const __m256i upper_lo = _mm256_set1_epi8('A' - 1);
    const __m256i upper_hi = _mm256_set1_epi8('Z' + 1);
    const __m256i lower_lo = _mm256_set1_epi8('a' - 1);
    const __m256i lower_hi = _mm256_set1_epi8('z' + 1);
    const __m256i digit_lo = _mm256_set1_epi8('0' - 1);
    const __m256i digit_hi = _mm256_set1_epi8('9' + 1);
    const __m256i plus = _mm256_set1_epi8('+');
    const __m256i slash = _mm256_set1_epi8('/');
    const __m256i zero = _mm256_setzero_si256();
    const __m256i sixty_two = _mm256_set1_epi8(62);
    const __m256i sixty_three = _mm256_set1_epi8(63);

    std::size_t out_offset = 0;
    for (std::size_t i = 0; i + 32 <= chars; i += 32) {
        __m256i x;
        std::memcpy(&x, src + i, sizeof(x));

        const __m256i upper = _mm256_and_si256(
            _mm256_cmpgt_epi8(x, upper_lo), _mm256_cmpgt_epi8(upper_hi, x));
        const __m256i lower = _mm256_and_si256(
            _mm256_cmpgt_epi8(x, lower_lo), _mm256_cmpgt_epi8(lower_hi, x));
        const __m256i digits = _mm256_and_si256(
            _mm256_cmpgt_epi8(x, digit_lo), _mm256_cmpgt_epi8(digit_hi, x));

        __m256i values = _mm256_blendv_epi8(
            zero, _mm256_sub_epi8(x, _mm256_set1_epi8('A')), upper);
        values = _mm256_blendv_epi8(
            values, _mm256_sub_epi8(x, _mm256_set1_epi8('a' - 26)), lower);
        values = _mm256_blendv_epi8(
            values, _mm256_add_epi8(x, _mm256_set1_epi8(4)), digits);
        values = _mm256_blendv_epi8(
            values, sixty_two, _mm256_cmpeq_epi8(x, plus));
        values = _mm256_blendv_epi8(
            values, sixty_three, _mm256_cmpeq_epi8(x, slash));

        unsigned char sextets[32];
        std::memcpy(sextets, &values, sizeof(sextets));
        for (std::size_t j = 0; j < 32; j += 4) {
            const unsigned int a = sextets[j];
            const unsigned int b = sextets[j + 1];
            const unsigned int c = sextets[j + 2];
            const unsigned int d = sextets[j + 3];
            dst[out_offset++] = static_cast<unsigned char>((a << 2) | (b >> 4));
            dst[out_offset++] = static_cast<unsigned char>((b << 4) | (c >> 2));
            dst[out_offset++] = static_cast<unsigned char>((c << 6) | d);
        }
    }
}

extern "C" void run(const void* input1, const void* input2, void* output,
                     int n, int parameter, int threads) {
    (void)input2;
    (void)parameter;
    (void)threads;

    auto* out = static_cast<unsigned char*>(output);
    std::memset(out + 8, 0, 8);

    if (n < 0 || (n & 3) != 0) {
        const std::uint64_t invalid = ~std::uint64_t{0};
        std::memcpy(out, &invalid, sizeof(invalid));
        return;
    }

    const std::size_t length = static_cast<std::size_t>(n);
    const auto* src = static_cast<const unsigned char*>(input1);
    unsigned char* payload = out + 16;

    // Keep the final quartet for scalar handling of optional padding.
    const std::size_t vector_chars = length >= 4
        ? ((length - 4) / 32) * 32
        : 0;
    if (vector_chars != 0) {
        decode_avx2_blocks(src, payload, vector_chars);
    }

    std::size_t written = (vector_chars / 4) * 3;
    for (std::size_t i = vector_chars; i + 4 <= length; i += 4) {
        const unsigned int a = b64_value(src[i]);
        const unsigned int b = b64_value(src[i + 1]);
        const unsigned char c2 = src[i + 2];
        const unsigned char c3 = src[i + 3];
        const unsigned int c = b64_value(c2);
        const unsigned int d = b64_value(c3);
        const bool last = i + 4 == length;

        payload[written++] = static_cast<unsigned char>((a << 2) | (b >> 4));
        if (last && c2 == '=') break;
        payload[written++] = static_cast<unsigned char>((b << 4) | (c >> 2));
        if (last && c3 == '=') break;
        payload[written++] = static_cast<unsigned char>((c << 6) | d);
    }

    const std::uint64_t decoded = static_cast<std::uint64_t>(written);
    std::memcpy(out, &decoded, sizeof(decoded));
}
