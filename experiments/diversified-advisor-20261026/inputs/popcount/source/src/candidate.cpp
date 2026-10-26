/*
 * Copyright (c) 2007 Bart Massey
 * [This program is licensed under the "MIT License"]
 * Please see the file LICENSE in the source
 * distribution of this software for license terms.
 */

#include <cstdint>
static inline uint32_t
popcount_naive(uint32_t n) {
    uint32_t c = 0;
    while (n) {
	c += n & 1;
	n >>= 1;
    }
    return c;
}
#include <cstdint>
#include <cstring>
#include <cmath>
#include <algorithm>
#include <omp.h>
extern "C" void run(const void* input1,const void* input2,void* output,int n,int parameter,int threads)
{const uint32_t*a=(const uint32_t*)input1;uint32_t result=0;for(int j=0;j<parameter;j++)for(int i=0;i<n;i++)result+=popcount_naive(a[i]^result);*(uint32_t*)output=result;}
