/*
 * Copyright (c) 2007 Bart Massey
 * [This program is licensed under the "MIT License"]
 * Please see the file LICENSE in the source
 * distribution of this software for license terms.
 */

#include <cstdint>

static inline __attribute__((target("popcnt"))) std::uint32_t
popcount_naive(std::uint32_t n) {
    return static_cast<std::uint32_t>(
        __builtin_popcountll(static_cast<unsigned long long>(n)));
}

extern "C" __attribute__((target("popcnt"))) void
run(const void* input1, const void* input2, void* output,
    int n, int parameter, int threads) {
    const std::uint32_t* a = static_cast<const std::uint32_t*>(input1);
    std::uint32_t result = 0;

    for (int j = 0; j < parameter; ++j) {
        int i = 0;
        for (; n - i >= 6; i += 6) {
            result += popcount_naive(a[i] ^ result);
            result += popcount_naive(a[i + 1] ^ result);
            result += popcount_naive(a[i + 2] ^ result);
            result += popcount_naive(a[i + 3] ^ result);
            result += popcount_naive(a[i + 4] ^ result);
            result += popcount_naive(a[i + 5] ^ result);
        }
        for (; i < n; ++i) {
            result += popcount_naive(a[i] ^ result);
        }
    }

    *static_cast<std::uint32_t*>(output) = result;
}
