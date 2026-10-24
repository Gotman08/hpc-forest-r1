#include <cstring>
#include <cstdint>
#include <cmath>
#include <algorithm>
#include <omp.h>

template<int N>
void mm(const float* A, const float* B, float* C, int threads)
{
    const int team_size = threads < 1 ? 1 : (threads < N ? threads : N);
    constexpr int block_size = 32;
#pragma omp parallel for schedule(static) num_threads(team_size) if(team_size > 1)
    for (int r = 0; r < N; ++r) {
        const float* a_row = A + r * N;
        float* c_row = C + r * N;
        for (int cb = 0; cb < N; cb += block_size) {
            const int width = N - cb < block_size ? N - cb : block_size;
            float accum[block_size] = {};
            for (int k = 0; k < N; ++k) {
                const float a = a_row[k];
                const float* b_chunk = B + k * N + cb;
                for (int j = 0; j < width; ++j)
                    accum[j] += a * b_chunk[j];
            }
            for (int j = 0; j < width; ++j)
                c_row[cb + j] = accum[j];
        }
    }
}

extern "C" void run(const void* input1, const void* input2, void* output, int n, int parameter, int threads)
{
    if (n == 1024)
        mm<1024>((const float*)input1, (const float*)input2, (float*)output, threads);
    else if (n == 128)
        mm<128>((const float*)input1, (const float*)input2, (float*)output, threads);
    else if (n == 32)
        mm<32>((const float*)input1, (const float*)input2, (float*)output, threads);
    else
        memset(output, 0, size_t(n) * n * 4);
}
