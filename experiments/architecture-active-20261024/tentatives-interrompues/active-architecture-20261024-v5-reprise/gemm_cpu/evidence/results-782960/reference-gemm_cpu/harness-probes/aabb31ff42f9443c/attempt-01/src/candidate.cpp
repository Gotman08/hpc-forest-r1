#include <algorithm>

template<int N>
static void mm(const float* A, const float* B, float* C, int threads) {
    const int workers = threads > 0 ? std::min(threads, N) : 1;

#pragma omp parallel for schedule(static) num_threads(workers) if(workers > 1)
    for (int r = 0; r < N; ++r) {
        const float* a_row = A + r * N;
        float* c_row = C + r * N;

        // Each call overwrites its output, including when C contains prior data.
        for (int c = 0; c < N; ++c) {
            c_row[c] = 0.0f;
        }

        for (int k = 0; k < N; ++k) {
            const float aik = a_row[k];
            const float* b_row = B + k * N;
            for (int c = 0; c < N; ++c) {
                c_row[c] += aik * b_row[c];
            }
        }
    }
}

extern "C" void run(const void* input1, const void* input2, void* output,
                    int n, int parameter, int threads) {
    const float* A = static_cast<const float*>(input1);
    const float* B = static_cast<const float*>(input2);
    float* C = static_cast<float*>(output);

    if (n == 1024) {
        mm<1024>(A, B, C, threads);
    } else if (n == 128) {
        mm<128>(A, B, C, threads);
    } else if (n == 32) {
        mm<32>(A, B, C, threads);
    }
}
