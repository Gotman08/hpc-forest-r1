/*
 * Copyright (c) 2007 Bart Massey
 * [This program is licensed under the "MIT License"]
 * Please see the file LICENSE in the source
 * distribution of this software for license terms.
 */

#include <cstdint>
static inline uint32_t
popcount_builtin(uint32_t n) {
    return static_cast<uint32_t>(__builtin_popcount(n));
}
#include <cstdint>
#include <cstring>
#include <cmath>
#include <algorithm>
#include <omp.h>
extern "C" void run(const void* input1,const void* input2,void* output,int n,int parameter,int threads)
{
    const uint32_t* a = static_cast<const uint32_t*>(input1);
    uint32_t result = 0;
    for (int j = 0; j < parameter; j++)
        for (int i = 0; i < n; i++)
            result += popcount_builtin(a[i] ^ result);
    *static_cast<uint32_t*>(output) = result;
}
