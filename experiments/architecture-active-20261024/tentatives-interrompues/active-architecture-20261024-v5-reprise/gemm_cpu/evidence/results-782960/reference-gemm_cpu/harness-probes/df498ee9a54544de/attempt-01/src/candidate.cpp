#include <cstddef>
#include <cstring>
#include <omp.h>

template<int N>
static void mm(const float* A, const float* B, float* C, int n)
{
    const int extent = N != 0 ? N : n;
    for (int r = 0; r < extent; ++r) {
        const std::size_t row_offset = static_cast<std::size_t>(r) * extent;
        const float* a_row = A + row_offset;
        float* c_row = C + row_offset;
        for (int k = 0; k < extent; ++k) {
            const float aik = a_row[k];
            const float* b_row = B + static_cast<std::size_t>(k) * extent;
            #pragma omp simd
            for (int c = 0; c < extent; ++c) {
                c_row[c] += aik * b_row[c];
            }
        }
    }
}

extern "C" void run(const void* input1, const void* input2, void* output,
                    int n, int parameter, int threads)
{
    (void)parameter;
    (void)threads;
    const std::size_t extent = static_cast<std::size_t>(n);
    std::memset(output, 0, extent * extent * sizeof(float));

    const float* A = static_cast<const float*>(input1);
    const float* B = static_cast<const float*>(input2);
    float* C = static_cast<float*>(output);
    if (n == 1024) {
        mm<1024>(A, B, C, n);
    } else if (n == 128) {
        mm<128>(A, B, C, n);
    } else if (n == 32) {
        mm<32>(A, B, C, n);
    } else {
        mm<0>(A, B, C, n);
    }
}
