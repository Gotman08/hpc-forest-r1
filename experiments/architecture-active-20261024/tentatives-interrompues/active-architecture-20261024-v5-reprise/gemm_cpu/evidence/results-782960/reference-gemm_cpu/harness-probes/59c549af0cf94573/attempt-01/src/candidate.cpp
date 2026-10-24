#include <cstddef>
#include <cstring>

template<int N>
static void mm(int n, const float* A, const float* B, float* C, int team)
{
    const int size = N == 0 ? n : N;
#pragma omp parallel for schedule(static) num_threads(team) if(size >= 128 && team > 1)
    for (int r = 0; r < size; ++r) {
        for (int c = 0; c < size; ++c) {
            for (int k = 0; k < size; ++k) {
                C[r * size + c] += A[r * size + k] * B[k * size + c];
            }
        }
    }
}

extern "C" void run(const void* input1, const void* input2, void* output,
                     int n, int parameter, int threads)
{
    const std::size_t element_count = static_cast<std::size_t>(n) *
                                      static_cast<std::size_t>(n);
    std::memset(output, 0, element_count * sizeof(float));

    int team = threads > 0 ? threads : 1;
    if (team > 8) team = 8;
    if (team > n) team = n;
    if (team < 1) team = 1;

    const float* A = static_cast<const float*>(input1);
    const float* B = static_cast<const float*>(input2);
    float* C = static_cast<float*>(output);

    if (n == 1024) mm<1024>(n, A, B, C, team);
    else if (n == 128) mm<128>(n, A, B, C, team);
    else if (n == 32) mm<32>(n, A, B, C, team);
    else mm<0>(n, A, B, C, team);
}
