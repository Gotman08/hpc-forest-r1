/*
 * Copyright (c) 2007 Bart Massey
 * [This program is licensed under the "MIT License"]
 * Please see the file LICENSE in the source
 * distribution of this software for license terms.
 */

#include <cstdint>

static inline uint32_t
popcount_swar(uint32_t n) {
    n = n - ((n >> 1) & 0x55555555u);
    n = (n & 0x33333333u) + ((n >> 2) & 0x33333333u);
    n = (n + (n >> 4)) & 0x0f0f0f0fu;

    const uint32_t low_pair = (n & 0x000000ffu) + ((n >> 8) & 0x000000ffu);
    const uint32_t high_pair = ((n >> 16) & 0x000000ffu) + ((n >> 24) & 0x000000ffu);
    return low_pair + high_pair;
}

#include <cstring>
#include <cmath>
#include <algorithm>
#include <omp.h>

extern "C" void run(const void* input1, const void* input2, void* output, int n, int parameter, int threads) {
    const uint32_t* a = (const uint32_t*)input1;
    uint32_t result = 0;
    for (int j = 0; j < parameter; j++) {
        for (int i = 0; i < n; i++) {
            result += popcount_swar(a[i] ^ result);
        }
    }
    *(uint32_t*)output = result;
}
