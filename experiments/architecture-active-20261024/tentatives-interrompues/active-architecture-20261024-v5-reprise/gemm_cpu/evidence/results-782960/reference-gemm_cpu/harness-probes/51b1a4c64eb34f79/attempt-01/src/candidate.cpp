#include <algorithm>
#include <cstddef>
#include <cstring>

template<int N>
static void mm(const float* A, const float* B, float* C, int team_size)
{
    if (N >= 128 && team_size > 1) {
#pragma omp parallel for schedule(static) num_threads(team_size)
        for (int r = 0; r < N; ++r)
            for (int c = 0; c < N; ++c)
                for (int k = 0; k < N; ++k)
                    C[r * N + c] += A[r * N + k] * B[k * N + c];
    } else {
        for (int r = 0; r < N; ++r)
            for (int c = 0; c < N; ++c)
                for (int k = 0; k < N; ++k)
                    C[r * N + c] += A[r * N + k] * B[k * N + c];
    }
}

static void mm_generic(const float* A, const float* B, float* C, int n, int team_size)
{
    if (n >= 128 && team_size > 1) {
#pragma omp parallel for schedule(static) num_threads(team_size)
        for (int r = 0; r < n; ++r)
            for (int c = 0; c < n; ++c)
                for (int k = 0; k < n; ++k)
                    C[static_cast<std::size_t>(r) * n + c] +=
                        A[static_cast<std::size_t>(r) * n + k] *
                        B[static_cast<std::size_t>(k) * n + c];
    } else {
        for (int r = 0; r < n; ++r)
            for (int c = 0; c < n; ++c)
                for (int k = 0; k < n; ++k)
                    C[static_cast<std::size_t>(r) * n + c] +=
                        A[static_cast<std::size_t>(r) * n + k] *
                        B[static_cast<std::size_t>(k) * n + c];
    }
}

extern "C" void run(const void* input1, const void* input2, void* output,
                    int n, int parameter, int threads)
{
    (void)parameter;
    std::memset(output, 0, static_cast<std::size_t>(n) *
                            static_cast<std::size_t>(n) * sizeof(float));

    const int team_size = std::min(std::max(threads, 1), std::min(4, n));
    const float* A = static_cast<const float*>(input1);
    const float* B = static_cast<const float*>(input2);
    float* C = static_cast<float*>(output);

    if (n == 1024)
        mm<1024>(A, B, C, team_size);
    else if (n == 128)
        mm<128>(A, B, C, team_size);
    else if (n == 32)
        mm<32>(A, B, C, team_size);
    else
        mm_generic(A, B, C, n, team_size);
}
