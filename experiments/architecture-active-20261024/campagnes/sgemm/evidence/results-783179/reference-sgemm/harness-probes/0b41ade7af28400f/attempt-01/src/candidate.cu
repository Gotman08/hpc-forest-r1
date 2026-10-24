#include <cstddef>
#include <cuda_runtime.h>

__global__ void sgemm_register_blocked(int M, int N, int K, float alpha,
                                       const float *A, const float *B,
                                       float beta, float *C) {
  const size_t row_count = static_cast<size_t>(M);
  const size_t col_count = static_cast<size_t>(N);
  const size_t first_row = static_cast<size_t>(blockIdx.y) * 4;
  const size_t row_stride = static_cast<size_t>(gridDim.y) * 4;
  const size_t first_col = static_cast<size_t>(blockIdx.x) * 256 +
                           static_cast<size_t>(threadIdx.x) * 8;

  for (size_t row_tile = first_row; row_tile < row_count;
       row_tile += row_stride) {
    const size_t row = row_tile + static_cast<size_t>(threadIdx.y);
    if (row >= row_count) continue;

    float acc[8] = {0.0f, 0.0f, 0.0f, 0.0f,
                    0.0f, 0.0f, 0.0f, 0.0f};
    for (int p = 0; p < K; ++p) {
      const float a = A[row * static_cast<size_t>(K) +
                        static_cast<size_t>(p)];
#pragma unroll
      for (int j = 0; j < 8; ++j) {
        const size_t col = first_col + static_cast<size_t>(j);
        if (col < col_count) {
          acc[j] += a * B[static_cast<size_t>(p) * col_count + col];
        }
      }
    }

#pragma unroll
    for (int j = 0; j < 8; ++j) {
      const size_t col = first_col + static_cast<size_t>(j);
      if (col < col_count) {
        const size_t idx = row * col_count + col;
        C[idx] = alpha * acc[j] + beta * C[idx];
      }
    }
  }
}

extern "C" void run(const float *A, const float *B, float *C, float *scratch,
                    int n, int m, int k, float alpha, float beta) {
  if (n <= 0 || m <= 0) return;
  const int blocks_x = m / 256 + (m % 256 != 0);
  int blocks_y = n / 4 + (n % 4 != 0);
  if (blocks_y > 65535) blocks_y = 65535;
  sgemm_register_blocked<<<dim3(blocks_x, blocks_y), dim3(32, 4)>>>(
      n, m, k, alpha, A, B, beta, C);
}
