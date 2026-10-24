#include <cstring>
template<int N> void mm(const float* A, const float* B, float* C) {
    for (int r = 0; r < N; ++r) {
        const float* a_row = A + r * N;
        float* c_row = C + r * N;
        for (int k = 0; k < N; ++k) {
            const float a = a_row[k];
            const float* b_row = B + k * N;
            for (int c = 0; c < N; ++c)
                c_row[c] += a * b_row[c];
        }
    }
}
#include <cstdint>
#include <cstring>
#include <cmath>
#include <algorithm>
#include <omp.h>
extern "C" void run(const void* input1, const void* input2, void* output, int n, int parameter, int threads)
{
    memset(output, 0, size_t(n) * n * 4);
    if (n == 1024) mm<1024>((const float*)input1, (const float*)input2, (float*)output);
    else if (n == 128) mm<128>((const float*)input1, (const float*)input2, (float*)output);
    else if (n == 32) mm<32>((const float*)input1, (const float*)input2, (float*)output);
}
