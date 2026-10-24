#include <cuda_runtime.h>
#include <stddef.h>

namespace {
constexpr int TILE_M = 16;
constexpr int TILE_N = 32;
constexpr int TILE_K = 32;
constexpr size_t MAX_CTA_COUNT = 65535;
}

__global__ void sgemm_shared_tiled(int M, int N, int K, float alpha,
                                   const float *A, const float *B, float beta,
                                   float *C) {
  __shared__ float shared_a[TILE_M][TILE_K];
  __shared__ float shared_b[TILE_K][TILE_N];

  const size_t rows = static_cast<size_t>(M);
  const size_t columns = static_cast<size_t>(N);
  const size_t reduction = static_cast<size_t>(K);
  const size_t tile_rows = rows / TILE_M + (rows % TILE_M != 0);
  const size_t tile_columns = columns / TILE_N + (columns % TILE_N != 0);
  const size_t total_tiles = tile_rows * tile_columns;
  const size_t thread_count = static_cast<size_t>(blockDim.x) * blockDim.y;
  const size_t thread_id = static_cast<size_t>(threadIdx.y) * blockDim.x +
                           threadIdx.x;

  for (size_t tile = static_cast<size_t>(blockIdx.x); tile < total_tiles;
       tile += static_cast<size_t>(gridDim.x)) {
    const size_t tile_row = tile / tile_columns;
    const size_t tile_column = tile % tile_columns;
    const size_t row_start = tile_row * TILE_M;
    const size_t column_start = tile_column * TILE_N;
    const size_t row = row_start + threadIdx.y;
    const size_t column = column_start + threadIdx.x;
    float sum = 0.0f;

    for (size_t k_start = 0; k_start < reduction; k_start += TILE_K) {
      for (size_t index = thread_id;
           index < static_cast<size_t>(TILE_M) * TILE_K;
           index += thread_count) {
        const size_t local_row = index / TILE_K;
        const size_t local_k = index % TILE_K;
        const size_t global_row = row_start + local_row;
        const size_t global_k = k_start + local_k;
        shared_a[local_row][local_k] =
            (global_row < rows && global_k < reduction)
                ? A[global_row * reduction + global_k]
                : 0.0f;
      }

      for (size_t index = thread_id;
           index < static_cast<size_t>(TILE_K) * TILE_N;
           index += thread_count) {
        const size_t local_k = index / TILE_N;
        const size_t local_column = index % TILE_N;
        const size_t global_k = k_start + local_k;
        const size_t global_column = column_start + local_column;
        shared_b[local_k][local_column] =
            (global_k < reduction && global_column < columns)
                ? B[global_k * columns + global_column]
                : 0.0f;
      }

      __syncthreads();

      const size_t remaining_k = reduction - k_start;
      const int active_k = remaining_k < TILE_K
                               ? static_cast<int>(remaining_k)
                               : TILE_K;
      for (int local_k = 0; local_k < active_k; ++local_k) {
        sum += shared_a[threadIdx.y][local_k] *
               shared_b[local_k][threadIdx.x];
      }

      __syncthreads();
    }

    if (row < rows && column < columns) {
      const size_t output_index = row * columns + column;
      C[output_index] = alpha * sum + beta * C[output_index];
    }
  }
}

extern "C" void run(const float *A, const float *B, float *C, float *scratch,
                    int n, int m, int k, float alpha, float beta) {
  if (n <= 0 || m <= 0) {
    return;
  }

  const size_t tile_rows = static_cast<size_t>(n) / TILE_M +
                           (n % TILE_M != 0);
  const size_t tile_columns = static_cast<size_t>(m) / TILE_N +
                              (m % TILE_N != 0);
  const size_t total_tiles = tile_rows * tile_columns;
  const size_t grid_size = total_tiles < MAX_CTA_COUNT
                               ? total_tiles
                               : MAX_CTA_COUNT;

  sgemm_shared_tiled<<<dim3(static_cast<unsigned int>(grid_size), 1, 1),
                       dim3(TILE_N, TILE_M, 1)>>>(n, m, k, alpha, A, B, beta,
                                                 C);
}
