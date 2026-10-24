#include <cstdio>
#include <cstdlib>
#include <cublas_v2.h>
#include <cuda_runtime.h>
#include <cstddef>

constexpr int TILE_M = 64;
constexpr int TILE_N = 64;
constexpr int TILE_K = 96;
constexpr int THREADS_X = 32;
constexpr int THREADS_Y = 8;
constexpr int ROWS_PER_THREAD = TILE_M / THREADS_Y;

__global__ void sgemm_tiled_64x64x96(int M, int N, int K, float alpha,
                                    const float *A, const float *B,
                                    float beta, float *C) {
  __shared__ float a_tile[TILE_M][TILE_K];
  __shared__ float b_tile[TILE_K][TILE_N];

  const int tx = threadIdx.x;
  const int ty = threadIdx.y;
  const int tid = ty * THREADS_X + tx;
  const int row_base = blockIdx.y * TILE_M;
  const int col_base = blockIdx.x * TILE_N;

  float accum[ROWS_PER_THREAD][2] = {};

  for (int k_base = 0; k_base < K; k_base += TILE_K) {
    for (int elem = tid; elem < TILE_M * TILE_K;
         elem += THREADS_X * THREADS_Y) {
      const int a_row = elem / TILE_K;
      const int a_k = elem % TILE_K;
      const int global_row = row_base + a_row;
      const int global_k = k_base + a_k;
      a_tile[a_row][a_k] =
          (global_row < M && global_k < K)
              ? A[static_cast<std::size_t>(global_row) * K + global_k]
              : 0.0f;

      const int b_k = elem / TILE_N;
      const int b_col = elem % TILE_N;
      const int global_b_k = k_base + b_k;
      const int global_col = col_base + b_col;
      b_tile[b_k][b_col] =
          (global_b_k < K && global_col < N)
              ? B[static_cast<std::size_t>(global_b_k) * N + global_col]
              : 0.0f;
    }

    __syncthreads();

    #pragma unroll 4
    for (int kk = 0; kk < TILE_K; ++kk) {
      const float b0 = b_tile[kk][tx];
      const float b1 = b_tile[kk][tx + THREADS_X];
      #pragma unroll
      for (int i = 0; i < ROWS_PER_THREAD; ++i) {
        const float a = a_tile[ty + i * THREADS_Y][kk];
        accum[i][0] = fmaf(a, b0, accum[i][0]);
        accum[i][1] = fmaf(a, b1, accum[i][1]);
      }
    }

    __syncthreads();
  }

  #pragma unroll
  for (int i = 0; i < ROWS_PER_THREAD; ++i) {
    const int row = row_base + ty + i * THREADS_Y;
    const int col0 = col_base + tx;
    const int col1 = col0 + THREADS_X;
    if (row < M && col0 < N) {
      const std::size_t index = static_cast<std::size_t>(row) * N + col0;
      C[index] = alpha * accum[i][0] + beta * C[index];
    }
    if (row < M && col1 < N) {
      const std::size_t index = static_cast<std::size_t>(row) * N + col1;
      C[index] = alpha * accum[i][1] + beta * C[index];
    }
  }
}

extern "C" void run(const float *A, const float *B, float *C, float *scratch,
                    int n, int m, int k, float alpha, float beta) {
  sgemm_tiled_64x64x96<<<dim3((m + TILE_N - 1) / TILE_N,
                              (n + TILE_M - 1) / TILE_M),
                         dim3(THREADS_X, THREADS_Y)>>>(
      n, m, k, alpha, A, B, beta, C);
}
