#include <stddef.h>
#include <cuda_runtime.h>

__global__ void sgemm_microtile_2x2(int M, int N, int K, float alpha,
                                   const float *A, const float *B, float beta,
                                   float *C) {
  const size_t row0 = static_cast<size_t>(blockIdx.y) * 32u +
                      static_cast<size_t>(threadIdx.y) * 2u;
  const size_t row1 = row0 + 1u;
  const size_t col0 = static_cast<size_t>(blockIdx.x) * 32u +
                      static_cast<size_t>(threadIdx.x) * 2u;
  const size_t col1 = col0 + 1u;
  const bool valid_row0 = row0 < static_cast<size_t>(M);
  const bool valid_row1 = row1 < static_cast<size_t>(M);
  const bool valid_col0 = col0 < static_cast<size_t>(N);
  const bool valid_col1 = col1 < static_cast<size_t>(N);

  float acc00 = 0.0f;
  float acc01 = 0.0f;
  float acc10 = 0.0f;
  float acc11 = 0.0f;

  for (int kk = 0; kk < K; ++kk) {
    float a0 = 0.0f;
    float a1 = 0.0f;
    float b0 = 0.0f;
    float b1 = 0.0f;
    if (valid_row0) {
      a0 = A[row0 * static_cast<size_t>(K) + static_cast<size_t>(kk)];
    }
    if (valid_row1) {
      a1 = A[row1 * static_cast<size_t>(K) + static_cast<size_t>(kk)];
    }
    if (valid_col0) {
      b0 = B[static_cast<size_t>(kk) * static_cast<size_t>(N) + col0];
    }
    if (valid_col1) {
      b1 = B[static_cast<size_t>(kk) * static_cast<size_t>(N) + col1];
    }
    acc00 += a0 * b0;
    acc01 += a0 * b1;
    acc10 += a1 * b0;
    acc11 += a1 * b1;
  }

  if (valid_row0 && valid_col0) {
    const size_t index = row0 * static_cast<size_t>(N) + col0;
    C[index] = alpha * acc00 + beta * C[index];
  }
  if (valid_row0 && valid_col1) {
    const size_t index = row0 * static_cast<size_t>(N) + col1;
    C[index] = alpha * acc01 + beta * C[index];
  }
  if (valid_row1 && valid_col0) {
    const size_t index = row1 * static_cast<size_t>(N) + col0;
    C[index] = alpha * acc10 + beta * C[index];
  }
  if (valid_row1 && valid_col1) {
    const size_t index = row1 * static_cast<size_t>(N) + col1;
    C[index] = alpha * acc11 + beta * C[index];
  }
}

extern "C" void run(const float *A, const float *B, float *C, float *scratch,
                    int n, int m, int k, float alpha, float beta) {
  (void)scratch;
  if (n <= 0 || m <= 0) {
    return;
  }
  const unsigned int grid_x = static_cast<unsigned int>(m / 32 + (m % 32 != 0));
  const unsigned int grid_y = static_cast<unsigned int>(n / 32 + (n % 32 != 0));
  sgemm_microtile_2x2<<<dim3(grid_x, grid_y), dim3(16, 16)>>>(
      n, m, k, alpha, A, B, beta, C);
}
