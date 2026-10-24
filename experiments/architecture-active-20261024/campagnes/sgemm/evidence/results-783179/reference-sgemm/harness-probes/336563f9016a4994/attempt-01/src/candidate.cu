#include <cuda_runtime.h>

__global__ void sgemm_coalesced(int M, int N, int K, float alpha,
                                const float *A, const float *B, float beta,
                                float *C) {
  const int col = static_cast<int>(blockIdx.x * blockDim.x + threadIdx.x);
  const int row = static_cast<int>(blockIdx.y * blockDim.y + threadIdx.y);

  if (row < M && col < N) {
    float sum = 0.0f;
    const size_t a_row = static_cast<size_t>(row) * static_cast<size_t>(K);
    const size_t b_col = static_cast<size_t>(col);
    for (int p = 0; p < K; ++p) {
      sum += A[a_row + static_cast<size_t>(p)] *
             B[static_cast<size_t>(p) * static_cast<size_t>(N) + b_col];
    }
    const size_t c_index = static_cast<size_t>(row) * static_cast<size_t>(N) + b_col;
    C[c_index] = alpha * sum + beta * C[c_index];
  }
}

extern "C" void run(const float *A, const float *B, float *C, float *scratch,
                    int n, int m, int k, float alpha, float beta) {
  if (n <= 0 || m <= 0) {
    return;
  }
  const dim3 block(32, 32);
  const dim3 grid((m - 1) / 32 + 1, (n - 1) / 32 + 1);
  sgemm_coalesced<<<grid, block>>>(n, m, k, alpha, A, B, beta, C);
}
