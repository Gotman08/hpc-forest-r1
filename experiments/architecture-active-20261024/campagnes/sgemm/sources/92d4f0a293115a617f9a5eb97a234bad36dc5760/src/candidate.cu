#include <cstddef>
#include <cuda_runtime.h>

__global__ void sgemm_register_blocked(int M, int N, int K, float alpha,
                                       const float *A, const float *B,
                                       float beta, float *C) {
  const int col = static_cast<int>(blockIdx.x) * 32 + threadIdx.x;
  const int row_base = static_cast<int>(blockIdx.y) * 32 + threadIdx.y * 4;

  if (col < N && row_base < M) {
    const int r0 = row_base;
    const int r1 = row_base + 1;
    const int r2 = row_base + 2;
    const int r3 = row_base + 3;
    float acc0 = 0.0f;
    float acc1 = 0.0f;
    float acc2 = 0.0f;
    float acc3 = 0.0f;

    for (int p = 0; p < K; ++p) {
      const float b = B[static_cast<size_t>(p) * N + col];
      if (r0 < M) acc0 += A[static_cast<size_t>(r0) * K + p] * b;
      if (r1 < M) acc1 += A[static_cast<size_t>(r1) * K + p] * b;
      if (r2 < M) acc2 += A[static_cast<size_t>(r2) * K + p] * b;
      if (r3 < M) acc3 += A[static_cast<size_t>(r3) * K + p] * b;
    }

    if (r0 < M) {
      const size_t idx = static_cast<size_t>(r0) * N + col;
      C[idx] = alpha * acc0 + beta * C[idx];
    }
    if (r1 < M) {
      const size_t idx = static_cast<size_t>(r1) * N + col;
      C[idx] = alpha * acc1 + beta * C[idx];
    }
    if (r2 < M) {
      const size_t idx = static_cast<size_t>(r2) * N + col;
      C[idx] = alpha * acc2 + beta * C[idx];
    }
    if (r3 < M) {
      const size_t idx = static_cast<size_t>(r3) * N + col;
      C[idx] = alpha * acc3 + beta * C[idx];
    }
  }
}

extern "C" void run(const float *A, const float *B, float *C, float *scratch,
                    int n, int m, int k, float alpha, float beta) {
  if (n <= 0 || m <= 0) return;
  const int blocks_x = m / 32 + (m % 32 != 0);
  const int blocks_y = n / 32 + (n % 32 != 0);
  sgemm_register_blocked<<<dim3(blocks_x, blocks_y), dim3(32, 8)>>>(
      n, m, k, alpha, A, B, beta, C);
}
