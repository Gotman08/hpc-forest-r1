#include <cstddef>
#include <cstring>
#include <omp.h>

constexpr int ROW_BLOCK = 4;

template<int N>
void update_row_block(const float* A, const float* B, float* C, int block) {
    const int first_row = block * ROW_BLOCK;
    const int end_row = first_row + ROW_BLOCK < N ? first_row + ROW_BLOCK : N;
    const int row_count = end_row - first_row;
    const float* a_rows[ROW_BLOCK];
    float* c_rows[ROW_BLOCK];

    for (int i = 0; i < row_count; ++i) {
        const int r = first_row + i;
        a_rows[i] = A + r * N;
        c_rows[i] = C + r * N;
    }

    for (int k = 0; k < N; ++k) {
        const float* b_row = B + k * N;
        for (int i = 0; i < row_count; ++i) {
            const float a = a_rows[i][k];
            float* c_row = c_rows[i];
            for (int c = 0; c < N; ++c)
                c_row[c] += a * b_row[c];
        }
    }
}

template<int N>
void mm(const float* A, const float* B, float* C, int threads) {
    const int block_count = (N + ROW_BLOCK - 1) / ROW_BLOCK;
    int workers = 1;
    if (threads > 1)
        workers = threads < block_count ? threads : block_count;

    std::memset(C, 0, std::size_t(N) * N * sizeof(float));
    if (workers > 1) {
        #pragma omp parallel for num_threads(workers) schedule(static)
        for (int block = 0; block < block_count; ++block)
            update_row_block<N>(A, B, C, block);
    } else {
        for (int block = 0; block < block_count; ++block)
            update_row_block<N>(A, B, C, block);
    }
}

extern "C" void run(const void* input1, const void* input2, void* output,
                    int n, int parameter, int threads) {
    const float* A = static_cast<const float*>(input1);
    const float* B = static_cast<const float*>(input2);
    float* C = static_cast<float*>(output);
    if (n == 1024) mm<1024>(A, B, C, threads);
    else if (n == 128) mm<128>(A, B, C, threads);
    else if (n == 32) mm<32>(A, B, C, threads);
}
