#include <cstddef>
#include <cuda_runtime.h>

static constexpr int TILE_M = 32;
static constexpr int TILE_N = 32;
static constexpr int TILE_K = 16;
static constexpr int ROWS_PER_THREAD = 4;

__global__ void sgemm_register_blocked_shared(
    int M, int N, int K, float alpha, const float *A, const float *B,
    float beta, float *C) {
  const size_t col = static_cast<size_t>(blockIdx.x) * TILE_N + threadIdx.x;
  const size_t row_base = static_cast<size_t>(blockIdx.y) * TILE_M +
                          static_cast<size_t>(threadIdx.y) * ROWS_PER_THREAD;
  const size_t row0 = row_base;
  const size_t row1 = row_base + 1;
  const size_t row2 = row_base + 2;
  const size_t row3 = row_base + 3;

  __shared__ float staged_a[TILE_M][TILE_K];
  __shared__ float staged_b[TILE_K][TILE_N];

  float acc0 = 0.0f;
  float acc1 = 0.0f;
  float acc2 = 0.0f;
  float acc3 = 0.0f;

  const int linear_thread = static_cast<int>(threadIdx.y) * blockDim.x +
                            static_cast<int>(threadIdx.x);
  const int thread_count = static_cast<int>(blockDim.x * blockDim.y);
  const size_t size_M = static_cast<size_t>(M);
  const size_t size_N = static_cast<size_t>(N);
  const size_t size_K = static_cast<size_t>(K);
  const size_t tile_row_base = static_cast<size_t>(blockIdx.y) * TILE_M;
  const size_t tile_col_base = static_cast<size_t>(blockIdx.x) * TILE_N;

  for (int k0 = 0; k0 < K;) {
    const int k_remaining = K - k0;

    for (int idx = linear_thread; idx < TILE_M * TILE_K;
         idx += thread_count) {
      const int a_row = idx / TILE_K;
      const int a_k = idx % TILE_K;
      const size_t global_row = tile_row_base + static_cast<size_t>(a_row);
      if (global_row < size_M && a_k < k_remaining) {
        const size_t global_k = static_cast<size_t>(k0) +
                                static_cast<size_t>(a_k);
        staged_a[a_row][a_k] = A[global_row * size_K + global_k];
      } else {
        staged_a[a_row][a_k] = 0.0f;
      }
    }

    for (int idx = linear_thread; idx < TILE_K * TILE_N;
         idx += thread_count) {
      const int b_k = idx / TILE_N;
      const int b_col = idx % TILE_N;
      const size_t global_col = tile_col_base + static_cast<size_t>(b_col);
      if (b_k < k_remaining && global_col < size_N) {
        const size_t global_k = static_cast<size_t>(k0) +
                                static_cast<size_t>(b_k);
        staged_b[b_k][b_col] = B[global_k * size_N + global_col];
      } else {
        staged_b[b_k][b_col] = 0.0f;
      }
    }

    __syncthreads();

    const int local_row_base = static_cast<int>(threadIdx.y) * ROWS_PER_THREAD;
    for (int kk = 0; kk < TILE_K; ++kk) {
      const float b = staged_b[kk][threadIdx.x];
      acc0 += staged_a[local_row_base][kk] * b;
      acc1 += staged_a[local_row_base + 1][kk] * b;
      acc2 += staged_a[local_row_base + 2][kk] * b;
      acc3 += staged_a[local_row_base + 3][kk] * b;
    }

    __syncthreads();
    if (k_remaining <= TILE_K) {
      break;
    }
    k0 += TILE_K;
  }

  if (col < size_N && row0 < size_M) {
    const size_t idx = row0 * size_N + col;
    C[idx] = alpha * acc0 + beta * C[idx];
  }
  if (col < size_N && row1 < size_M) {
    const size_t idx = row1 * size_N + col;
    C[idx] = alpha * acc1 + beta * C[idx];
  }
  if (col < size_N && row2 < size_M) {
    const size_t idx = row2 * size_N + col;
    C[idx] = alpha * acc2 + beta * C[idx];
  }
  if (col < size_N && row3 < size_M) {
    const size_t idx = row3 * size_N + col;
    C[idx] = alpha * acc3 + beta * C[idx];
  }
}

extern "C" void run(const float *A, const float *B, float *C, float *scratch,
                    int n, int m, int k, float alpha, float beta) {
  (void)scratch;
  if (n <= 0 || m <= 0) {
    return;
  }

  const int blocks_x = m / TILE_N + (m % TILE_N != 0);
  const int blocks_y = n / TILE_M + (n % TILE_M != 0);
  sgemm_register_blocked_shared<<<dim3(blocks_x, blocks_y), dim3(32, 8)>>>(
      n, m, k, alpha, A, B, beta, C);
}
