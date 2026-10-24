/*
 * Copyright (c) 2007 Bart Massey
 * [This program is licensed under the "MIT License"]
 * Please see the file LICENSE in the source
 * distribution of this software for license terms.
 */

#include <cstdint>
static inline uint32_t
popcount_swar(uint32_t n) {
    // Count the bits independently in each 4-bit group.
    n = n - ((n >> 1) & 0x77777777u)
          - ((n >> 2) & 0x33333333u)
          - ((n >> 3) & 0x11111111u);

    // Combine each pair of nibble counts, then sum the four byte counts.
    n = (n + (n >> 4)) & 0x0F0F0F0Fu;
    return (n * 0x01010101u) >> 24;
}
#include <cstdint>
#include <cstring>
#include <cmath>
#include <algorithm>
#include <omp.h>
extern "C" void run(const void* input1,const void* input2,void* output,int n,int parameter,int threads)
{const uint32_t*a=(const uint32_t*)input1;uint32_t result=0;for(int j=0;j<parameter;j++)for(int i=0;i<n;i++)result+=popcount_swar(a[i]^result);*(uint32_t*)output=result;}
