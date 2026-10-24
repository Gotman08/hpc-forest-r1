/*
 * Copyright (c) 2007 Bart Massey
 * [This program is licensed under the "MIT License"]
 * Please see the file LICENSE in the source
 * distribution of this software for license terms.
 */

#include <cstdint>
#include <cstring>
#include <cmath>
#include <algorithm>
#include <omp.h>

extern "C" __attribute__((target("popcnt")))
void run(const void* input1, const void* input2, void* output,
         int n, int parameter, int threads)
{
    const std::uint32_t* a = static_cast<const std::uint32_t*>(input1);
    std::uint32_t result = 0;

    for (int j = 0; j < parameter; ++j) {
        for (int i = 0; i < n; ++i) {
            result += static_cast<std::uint32_t>(__builtin_popcount(
                static_cast<unsigned int>(a[i] ^ result)));
        }
    }

    *static_cast<std::uint32_t*>(output) = result;
}
