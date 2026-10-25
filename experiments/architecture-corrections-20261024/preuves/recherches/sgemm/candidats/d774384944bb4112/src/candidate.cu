#include <cuda_runtime.h>
#include <stddef.h>

namespace {
constexpr int TILE_M = 64;
constexpr int TILE_N = 32;
constexpr int TILE_K = 32;
constexpr int THREADS_X = 32;
constexpr int THREADS_Y = 8;
constexpr int ROWS_PER_THREAD = 8;

__global__ void sgemm_tiled(int M, int N, int K, float alpha, const float *A,
                            const float *B, float beta, float *C) {
  __shared__ float shared_a[TILE_M * TILE_K];
  __shared__ float shared_b[TILE_K * TILE_N];

  const int lane_col = threadIdx.x;
  const int row_group = threadIdx.y;
  const int linear_thread = row_group * blockDim.x + lane_col;
  float accum[ROWS_PER_THREAD] = {};

  for (int k_base = 0; k_base < K; k_base += TILE_K) {
    for (int idx = linear_thread; idx < TILE_M * TILE_K;
         idx += THREADS_X * THREADS_Y) {
      const int local_row = idx / TILE_K;
      const int local_k = idx % TILE_K;
      const int global_row = blockIdx.y * TILE_M + local_row;
      const int global_k = k_base + local_k;
      shared_a[idx] = (global_row < M && global_k < K)
                          ? A[static_cast<size_t>(global_row) * K + global_k]
                          : 0.0f;
    }

    for (int idx = linear_thread; idx < TILE_K * TILE_N;
         idx += THREADS_X * THREADS_Y) {
      const int local_k = idx / TILE_N;
      const int local_col = idx % TILE_N;
      const int global_k = k_base + local_k;
      const int global_col = blockIdx.x * TILE_N + local_col;
      shared_b[idx] = (global_k < K && global_col < N)
                          ? B[static_cast<size_t>(global_k) * N + global_col]
                          : 0.0f;
    }

    __syncthreads();

    #pragma unroll
    for (int kk = 0; kk < TILE_K; ++kk) {
      const float b_value = shared_b[kk * TILE_N + lane_col];
      #pragma unroll
      for (int r = 0; r < ROWS_PER_THREAD; ++r) {
        const int local_row = row_group + r * THREADS_Y;
        const float a_value = shared_a[local_row * TILE_K + kk];
        accum[r] += a_value * b_value;
      }
    }

    __syncthreads();
  }

  const int global_col = blockIdx.x * TILE_N + lane_col;
  #pragma unroll
  for (int r = 0; r < ROWS_PER_THREAD; ++r) {
    const int global_row = blockIdx.y * TILE_M + row_group + r * THREADS_Y;
    if (global_row < M && global_col < N) {
      const size_t index = static_cast<size_t>(global_row) * N + global_col;
      float result = alpha * accum[r];
      if (beta != 0.0f) {
        result += beta * C[index];
      }
      C[index] = result;
    }
  }
}
}  // namespace

extern "C" void run(const float *A, const float *B, float *C, float *scratch,
                    int n, int m, int k, float alpha, float beta) {
  (void)scratch;
  if (n <= 0 || m <= 0) {
    return;
  }

  const int grid_x = m / TILE_N + (m % TILE_N != 0);
  const int grid_y = n / TILE_M + (n % TILE_M != 0);
  sgemm_tiled<<<dim3(grid_x, grid_y), dim3(THREADS_X, THREADS_Y)>>>(
      n, m, k, alpha, A, B, beta, C);
}
