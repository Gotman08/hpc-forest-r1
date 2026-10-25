#include <cuda_runtime.h>
#include <stdint.h>

namespace {
constexpr int BM = 64;
constexpr int BN = 64;
constexpr int BK = 64;
constexpr int THREAD_COLS = 32;
constexpr int THREAD_ROWS = 8;
constexpr int THREADS = THREAD_COLS * THREAD_ROWS;
constexpr int SHARED_BYTES = 2 * (BM * BK + BK * BN) * sizeof(float);

__device__ __forceinline__ bool aligned16(const void *ptr) {
  return (reinterpret_cast<uintptr_t>(ptr) & static_cast<uintptr_t>(15)) == 0;
}

__device__ __forceinline__ void copy_async4(float *dst, const float *src) {
  const unsigned int shared_address =
      static_cast<unsigned int>(__cvta_generic_to_shared(dst));
  asm volatile("cp.async.ca.shared.global [%0], [%1], 4;"
               :
               : "r"(shared_address), "l"(src)
               : "memory");
}

__device__ __forceinline__ void copy_async16(float *dst, const float *src) {
  const unsigned int shared_address =
      static_cast<unsigned int>(__cvta_generic_to_shared(dst));
  asm volatile("cp.async.ca.shared.global [%0], [%1], 16;"
               :
               : "r"(shared_address), "l"(src)
               : "memory");
}

__device__ __forceinline__ void commit_async_copies() {
  asm volatile("cp.async.commit_group;" ::: "memory");
}

__device__ __forceinline__ void wait_async_copies() {
  asm volatile("cp.async.wait_group 0;" ::: "memory");
}

__device__ __forceinline__ void stage_tile_async(
    int M, int N, int K, const float *A, const float *B, int block_row,
    int block_col, int k_origin, float *tile_a, float *tile_b) {
  const int tid = static_cast<int>(threadIdx.y) * THREAD_COLS +
                  static_cast<int>(threadIdx.x);

  constexpr int A_GROUPS = BM * (BK / 4);
  for (int group = tid; group < A_GROUPS; group += THREADS) {
    const int row_in_tile = group / (BK / 4);
    const int k_in_tile = (group % (BK / 4)) * 4;
    const int row = block_row + row_in_tile;
    const int global_k = k_origin + k_in_tile;
    float *dst = tile_a + row_in_tile * BK + k_in_tile;

    if (row < M && global_k < K) {
      const float *src =
          A + static_cast<unsigned long long>(row) * K + global_k;
      if (K - global_k >= 4 && aligned16(src) && aligned16(dst)) {
        copy_async16(dst, src);
      } else {
#pragma unroll
        for (int j = 0; j < 4; ++j) {
          if (global_k + j < K) {
            copy_async4(dst + j, src + j);
          } else {
            dst[j] = 0.0f;
          }
        }
      }
    } else {
#pragma unroll
      for (int j = 0; j < 4; ++j) {
        dst[j] = 0.0f;
      }
    }
  }

  constexpr int B_GROUPS = BK * (BN / 4);
  for (int group = tid; group < B_GROUPS; group += THREADS) {
    const int k_in_tile = group / (BN / 4);
    const int col_in_tile = (group % (BN / 4)) * 4;
    const int global_k = k_origin + k_in_tile;
    const int col = block_col + col_in_tile;
    float *dst = tile_b + k_in_tile * BN + col_in_tile;

    if (global_k < K && col < N) {
      const float *src =
          B + static_cast<unsigned long long>(global_k) * N + col;
      if (N - col >= 4 && aligned16(src) && aligned16(dst)) {
        copy_async16(dst, src);
      } else {
#pragma unroll
        for (int j = 0; j < 4; ++j) {
          if (col + j < N) {
            copy_async4(dst + j, src + j);
          } else {
            dst[j] = 0.0f;
          }
        }
      }
    } else {
#pragma unroll
      for (int j = 0; j < 4; ++j) {
        dst[j] = 0.0f;
      }
    }
  }
}
}  // namespace

__global__ void sgemm_tiled_async(int M, int N, int K, float alpha,
                                  const float *A, const float *B, float beta,
                                  float *C) {
  extern __shared__ __align__(16) float shared_storage[];
  float *tileA0 = shared_storage;
  float *tileB0 = tileA0 + BM * BK;
  float *tileA1 = tileB0 + BK * BN;
  float *tileB1 = tileA1 + BM * BK;

  const int tx = static_cast<int>(threadIdx.x);
  const int ty = static_cast<int>(threadIdx.y);
  const int block_row = static_cast<int>(blockIdx.y) * BM;
  const int block_col = static_cast<int>(blockIdx.x) * BN;
  const int k_tiles = K > 0 ? K / BK + ((K % BK) != 0) : 0;

  float accum[8][2] = {};

  if (k_tiles > 0) {
    stage_tile_async(M, N, K, A, B, block_row, block_col, 0, tileA0, tileB0);
    commit_async_copies();
    wait_async_copies();
    __syncthreads();

    int current = 0;
    for (int tile = 0; tile < k_tiles; ++tile) {
      const bool has_next = tile + 1 < k_tiles;
      const int next = current ^ 1;
      float *current_a = current == 0 ? tileA0 : tileA1;
      float *current_b = current == 0 ? tileB0 : tileB1;
      float *next_a = next == 0 ? tileA0 : tileA1;
      float *next_b = next == 0 ? tileB0 : tileB1;

      if (has_next) {
        stage_tile_async(M, N, K, A, B, block_row, block_col,
                         (tile + 1) * BK, next_a, next_b);
        commit_async_copies();
      }

      for (int kk = 0; kk < BK; ++kk) {
        const int b_index = kk * BN + tx;
        const float b0 = current_b[b_index];
        const float b1 = current_b[b_index + THREAD_COLS];
#pragma unroll
        for (int r = 0; r < 8; ++r) {
          const int a_index = (ty + r * THREAD_ROWS) * BK + kk;
          const float a = current_a[a_index];
          accum[r][0] += a * b0;
          accum[r][1] += a * b1;
        }
      }

      if (has_next) {
        wait_async_copies();
        __syncthreads();
        current = next;
      }
    }
  }

#pragma unroll
  for (int r = 0; r < 8; ++r) {
    const int row = block_row + ty + r * THREAD_ROWS;
    const int col0 = block_col + tx;
    const int col1 = col0 + THREAD_COLS;
    if (row < M) {
      if (col0 < N) {
        const unsigned long long index =
            static_cast<unsigned long long>(row) * N + col0;
        if (beta == 0.0f) {
          C[index] = alpha * accum[r][0];
        } else {
          C[index] = alpha * accum[r][0] + beta * C[index];
        }
      }
      if (col1 < N) {
        const unsigned long long index =
            static_cast<unsigned long long>(row) * N + col1;
        if (beta == 0.0f) {
          C[index] = alpha * accum[r][1];
        } else {
          C[index] = alpha * accum[r][1] + beta * C[index];
        }
      }
    }
  }
}

extern "C" void run(const float *A, const float *B, float *C, float *scratch,
                    int n, int m, int k, float alpha, float beta) {
  (void)scratch;
  if (n <= 0 || m <= 0) {
    return;
  }

  cudaFuncSetAttribute(sgemm_tiled_async,
                       cudaFuncAttributeMaxDynamicSharedMemorySize,
                       SHARED_BYTES);
  const dim3 grid(static_cast<unsigned int>((m - 1) / BN + 1),
                  static_cast<unsigned int>((n - 1) / BM + 1));
  const dim3 block(THREAD_COLS, THREAD_ROWS);
  sgemm_tiled_async<<<grid, block, SHARED_BYTES>>>(n, m, k, alpha, A, B, beta,
                                                  C);
}
