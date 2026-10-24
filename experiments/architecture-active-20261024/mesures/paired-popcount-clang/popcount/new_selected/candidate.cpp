/*
 * Copyright (c) 2007 Bart Massey
 * [This program is licensed under the "MIT License"]
 * Please see the file LICENSE in the source
 * distribution of this software for license terms.
 */

#include <cstdint>

static inline uint32_t popcount_builtin(uint32_t value)
{
    return static_cast<uint32_t>(__builtin_popcount(value));
}

extern "C" void run(const void* input1, const void* input2, void* output,
                    int n, int parameter, int threads)
{
    const uint32_t* a = static_cast<const uint32_t*>(input1);
    uint32_t result = 0;

    for (int j = 0; j < parameter; ++j) {
        int i = 0;
        for (; n - i >= 4; i += 4) {
            result += popcount_builtin(a[i] ^ result);
            result += popcount_builtin(a[i + 1] ^ result);
            result += popcount_builtin(a[i + 2] ^ result);
            result += popcount_builtin(a[i + 3] ^ result);
        }
        for (; i < n; ++i) {
            result += popcount_builtin(a[i] ^ result);
        }
    }

    *static_cast<uint32_t*>(output) = result;
}
