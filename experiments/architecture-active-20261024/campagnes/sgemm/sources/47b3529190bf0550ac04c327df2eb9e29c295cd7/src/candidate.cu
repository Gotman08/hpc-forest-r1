#include <cuda_runtime.h>
#include <stddef.h>

namespace {
constexpr int TILE_M = 16;
constexpr int TILE_N = 32;
constexpr int TILE_K = 16;

__global__ void sgemm_tiled(int M, int N, int K, float alpha,
                            const float *A, const float *B, float beta,
                            float *C) {
  __shared__ float tile_a[TILE_M][TILE_K];
  __shared__ float tile_b[TILE_K][TILE_N];

  const int local_row = threadIdx.y;
  const int local_col = threadIdx.x;
  const size_t row = static_cast<size_t>(blockIdx.y) * TILE_M + local_row;
  const size_t col = static_cast<size_t>(blockIdx.x) * TILE_N + local_col;
  const size_t k_extent = K > 0 ? static_cast<size_t>(K) : 0;
  const int tid = local_row * TILE_N + local_col;
  float accum = 0.0f;

  for (size_t k_base = 0; k_base < k_extent; k_base += TILE_K) {
    for (int elem = tid; elem < TILE_M * TILE_K;
         elem += TILE_M * TILE_N) {
      const int a_row = elem / TILE_K;
      const int a_k = elem % TILE_K;
      const size_t global_row =
          static_cast<size_t>(blockIdx.y) * TILE_M + a_row;
      const size_t global_k = k_base + static_cast<size_t>(a_k);
      tile_a[a_row][a_k] =
          (global_row < static_cast<size_t>(M) && global_k < k_extent)
              ? A[global_row * static_cast<size_t>(K) + global_k]
              : 0.0f;
    }

    for (int elem = tid; elem < TILE_K * TILE_N;
         elem += TILE_M * TILE_N) {
      const int b_k = elem / TILE_N;
      const int b_col = elem % TILE_N;
      const size_t global_k = k_base + static_cast<size_t>(b_k);
      const size_t global_col =
          static_cast<size_t>(blockIdx.x) * TILE_N + b_col;
      tile_b[b_k][b_col] =
          (global_k < k_extent && global_col < static_cast<size_t>(N))
              ? B[global_k * static_cast<size_t>(N) + global_col]
              : 0.0f;
    }

    __syncthreads();
    if (row < static_cast<size_t>(M) && col < static_cast<size_t>(N)) {
#pragma unroll
      for (int kk = 0; kk < TILE_K; ++kk) {
        accum += tile_a[local_row][kk] * tile_b[kk][local_col];
      }
    }
    __syncthreads();
  }

  if (row < static_cast<size_t>(M) && col < static_cast<size_t>(N)) {
    const size_t index = row * static_cast<size_t>(N) + col;
    C[index] = alpha * accum + beta * C[index];
  }
}
}  // namespace

extern "C" void run(const float *A, const float *B, float *C, float *scratch,
                    int n, int m, int k, float alpha, float beta) {
  (void)scratch;
  if (n <= 0 || m <= 0) {
    return;
  }

  const unsigned int grid_x =
      static_cast<unsigned int>(m / TILE_N + (m % TILE_N != 0));
  const unsigned int grid_y =
      static_cast<unsigned int>(n / TILE_M + (n % TILE_M != 0));
  sgemm_tiled<<<dim3(grid_x, grid_y), dim3(TILE_N, TILE_M)>>>(
      n, m, k, alpha, A, B, beta, C);
}
