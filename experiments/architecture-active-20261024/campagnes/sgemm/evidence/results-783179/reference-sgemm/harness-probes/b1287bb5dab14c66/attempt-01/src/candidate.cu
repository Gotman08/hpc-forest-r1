#include <cuda_runtime.h>
#include <stddef.h>

namespace {

constexpr int TILE = 16;

__device__ __forceinline__ void copy_float_to_shared(float *dst,
                                                     const float *src) {
#if defined(__CUDA_ARCH__) && __CUDA_ARCH__ >= 800
  const unsigned int shared_addr = static_cast<unsigned int>(
      __cvta_generic_to_shared(dst));
  // Float pointers and shared float elements are 4-byte aligned.
  asm volatile("cp.async.ca.shared.global [%0], [%1], 4;"
               :
               : "r"(shared_addr), "l"(src)
               : "memory");
#else
  *dst = *src;
#endif
}

__device__ __forceinline__ void commit_async_copies() {
#if defined(__CUDA_ARCH__) && __CUDA_ARCH__ >= 800
  asm volatile("cp.async.commit_group;" ::: "memory");
#endif
}

__device__ __forceinline__ void wait_async_copies() {
#if defined(__CUDA_ARCH__) && __CUDA_ARCH__ >= 800
  asm volatile("cp.async.wait_group 0;" ::: "memory");
#endif
}

__device__ __forceinline__ void stage_k_tile(
    float a_stage[TILE][TILE], float b_stage[TILE][TILE], int M, int N,
    int K, int k_base, const float *A, const float *B) {
  const int ty = threadIdx.y;
  const int tx = threadIdx.x;
  const size_t row = static_cast<size_t>(blockIdx.x) * TILE + ty;
  const size_t col = static_cast<size_t>(blockIdx.y) * TILE + tx;
  const size_t a_k = static_cast<size_t>(k_base) + tx;
  const size_t b_k = static_cast<size_t>(k_base) + ty;

  if (row < static_cast<size_t>(M) && a_k < static_cast<size_t>(K)) {
    copy_float_to_shared(&a_stage[ty][tx],
                         A + row * static_cast<size_t>(K) + a_k);
  } else {
    a_stage[ty][tx] = 0.0f;
  }

  if (b_k < static_cast<size_t>(K) && col < static_cast<size_t>(N)) {
    copy_float_to_shared(&b_stage[ty][tx],
                         B + b_k * static_cast<size_t>(N) + col);
  } else {
    b_stage[ty][tx] = 0.0f;
  }
}

__global__ void sgemm_tiled_async(int M, int N, int K, float alpha,
                                  const float *A, const float *B, float beta,
                                  float *C) {
  __shared__ float shared_a[2][TILE][TILE];
  __shared__ float shared_b[2][TILE][TILE];

  const int ty = threadIdx.y;
  const int tx = threadIdx.x;
  const int k_tiles = K > 0 ? K / TILE + (K % TILE != 0) : 0;
  float accum = 0.0f;
  int current = 0;

  if (k_tiles > 0) {
    stage_k_tile(shared_a[current], shared_b[current], M, N, K, 0, A, B);
    commit_async_copies();
    wait_async_copies();
    __syncthreads();
  }

  for (int tile = 0; tile < k_tiles; ++tile) {
    const bool has_next = tile + 1 < k_tiles;
    const int next = current ^ 1;

    if (has_next) {
      const int next_k_base = (tile + 1) * TILE;
      stage_k_tile(shared_a[next], shared_b[next], M, N, K, next_k_base,
                   A, B);
      commit_async_copies();
    }

    for (int q = 0; q < TILE; ++q) {
      accum += shared_a[current][ty][q] * shared_b[current][q][tx];
    }

    if (has_next) {
      wait_async_copies();
      // Wait for both the incoming copies and every thread's use of the
      // current buffer before it can be reused by a later stage.
      __syncthreads();
      current = next;
    }
  }

  const size_t row = static_cast<size_t>(blockIdx.x) * TILE + ty;
  const size_t col = static_cast<size_t>(blockIdx.y) * TILE + tx;
  if (row < static_cast<size_t>(M) && col < static_cast<size_t>(N)) {
    const size_t c_index = row * static_cast<size_t>(N) + col;
    C[c_index] = alpha * accum + beta * C[c_index];
  }
}

}  // namespace

extern "C" void run(const float *A, const float *B, float *C, float *scratch,
                    int n, int m, int k, float alpha, float beta) {
  (void)scratch;
  if (n <= 0 || m <= 0) {
    return;
  }
  const unsigned int grid_x = static_cast<unsigned int>(
      n / TILE + (n % TILE != 0));
  const unsigned int grid_y = static_cast<unsigned int>(
      m / TILE + (m % TILE != 0));
  sgemm_tiled_async<<<dim3(grid_x, grid_y), dim3(TILE, TILE)>>>(
      n, m, k, alpha, A, B, beta, C);
}
