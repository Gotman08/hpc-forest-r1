#include <cstddef>
#include <cuda_runtime.h>

__global__ void sgemm_register_blocked(int M, int N, int K, float alpha,
                                       const float *A, const float *B,
                                       float beta, float *C) {
  // Each 32-thread row computes four 32-column stripes. This keeps each
  // warp's accesses contiguous while reusing one A value across four outputs.
  const size_t row = static_cast<size_t>(blockIdx.y) * 8 + threadIdx.y;
  const size_t col0 = static_cast<size_t>(blockIdx.x) * 128 + threadIdx.x;
  const size_t col1 = col0 + 32;
  const size_t col2 = col0 + 64;
  const size_t col3 = col0 + 96;

  if (row >= static_cast<size_t>(M) || col0 >= static_cast<size_t>(N)) return;

  float acc0 = 0.0f;
  float acc1 = 0.0f;
  float acc2 = 0.0f;
  float acc3 = 0.0f;

  for (int p = 0; p < K; ++p) {
    const size_t b_row = static_cast<size_t>(p) * static_cast<size_t>(N);
    const float a = A[row * static_cast<size_t>(K) + static_cast<size_t>(p)];
    acc0 += a * B[b_row + col0];
    if (col1 < static_cast<size_t>(N)) acc1 += a * B[b_row + col1];
    if (col2 < static_cast<size_t>(N)) acc2 += a * B[b_row + col2];
    if (col3 < static_cast<size_t>(N)) acc3 += a * B[b_row + col3];
  }

  const size_t c_row = row * static_cast<size_t>(N);
  C[c_row + col0] = alpha * acc0 + beta * C[c_row + col0];
  if (col1 < static_cast<size_t>(N))
    C[c_row + col1] = alpha * acc1 + beta * C[c_row + col1];
  if (col2 < static_cast<size_t>(N))
    C[c_row + col2] = alpha * acc2 + beta * C[c_row + col2];
  if (col3 < static_cast<size_t>(N))
    C[c_row + col3] = alpha * acc3 + beta * C[c_row + col3];
}

extern "C" void run(const float *A, const float *B, float *C, float *scratch,
                    int n, int m, int k, float alpha, float beta) {
  if (n <= 0 || m <= 0) return;
  const int blocks_x = m / 128 + (m % 128 != 0);
  const int blocks_y = n / 8 + (n % 8 != 0);
  sgemm_register_blocked<<<dim3(blocks_x, blocks_y), dim3(32, 8)>>>(
      n, m, k, alpha, A, B, beta, C);
}
