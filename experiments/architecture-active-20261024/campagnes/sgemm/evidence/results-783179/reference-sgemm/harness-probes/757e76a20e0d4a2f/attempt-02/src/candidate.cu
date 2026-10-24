#include <cstddef>
#include <cuda_runtime.h>

namespace {

constexpr int TILE = 16;
constexpr int PIPE_STAGES = 3;

__device__ __forceinline__ void copy_float_to_shared(float *dst,
                                                     const float *src) {
#if defined(__CUDA_ARCH__) && __CUDA_ARCH__ >= 800
  const unsigned int shared_addr = static_cast<unsigned int>(
      __cvta_generic_to_shared(dst));
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

// Wait until at most keep_groups of the newest committed groups remain pending.
__device__ __forceinline__ void wait_async_copies(int keep_groups) {
#if defined(__CUDA_ARCH__) && __CUDA_ARCH__ >= 800
  if (keep_groups == 0) {
    asm volatile("cp.async.wait_group 0;" ::: "memory");
  } else if (keep_groups == 1) {
    asm volatile("cp.async.wait_group 1;" ::: "memory");
  } else {
    asm volatile("cp.async.wait_group 2;" ::: "memory");
  }
#else
  (void)keep_groups;
#endif
}

__device__ __forceinline__ void stage_k_tile(
    float a_stage[TILE][TILE], float b_stage[TILE][TILE], int M, int N,
    int K, int k_base, const float *A, const float *B) {
  const int ty = threadIdx.y;
  const int tx = threadIdx.x;
  const std::size_t row = static_cast<std::size_t>(blockIdx.y) * TILE + ty;
  const std::size_t col = static_cast<std::size_t>(blockIdx.x) * TILE + tx;
  const std::size_t a_k = static_cast<std::size_t>(k_base) + tx;
  const std::size_t b_k = static_cast<std::size_t>(k_base) + ty;

  if (row < static_cast<std::size_t>(M) && a_k < static_cast<std::size_t>(K)) {
    copy_float_to_shared(
        &a_stage[ty][tx],
        A + row * static_cast<std::size_t>(K) + a_k);
  } else {
    a_stage[ty][tx] = 0.0f;
  }

  if (b_k < static_cast<std::size_t>(K) && col < static_cast<std::size_t>(N)) {
    copy_float_to_shared(
        &b_stage[ty][tx],
        B + b_k * static_cast<std::size_t>(N) + col);
  } else {
    b_stage[ty][tx] = 0.0f;
  }
}

__global__ void sgemm_tiled_async(int M, int N, int K, float alpha,
                                  const float *A, const float *B, float beta,
                                  float *C) {
  __shared__ float shared_a[PIPE_STAGES][TILE][TILE];
  __shared__ float shared_b[PIPE_STAGES][TILE][TILE];

  const int ty = threadIdx.y;
  const int tx = threadIdx.x;
  const int k_tiles = K > 0 ? K / TILE + (K % TILE != 0) : 0;
  const int initial_stages = k_tiles < PIPE_STAGES ? k_tiles : PIPE_STAGES;
  float sum = 0.0f;

  // Prime up to three K stages so two future stages can be in flight while
  // the current tile is consumed.
  for (int preload = 0; preload < initial_stages; ++preload) {
    stage_k_tile(shared_a[preload], shared_b[preload], M, N, K,
                 preload * TILE, A, B);
    commit_async_copies();
  }

  for (int tile = 0; tile < k_tiles; ++tile) {
    int future_groups = k_tiles - tile - 1;
    if (future_groups > PIPE_STAGES - 1) {
      future_groups = PIPE_STAGES - 1;
    }
    wait_async_copies(future_groups);
    __syncthreads();

    const int slot = tile % PIPE_STAGES;
    for (int kk = 0; kk < TILE; ++kk) {
      sum += shared_a[slot][ty][kk] * shared_b[slot][kk][tx];
    }

    const int next_tile = tile + PIPE_STAGES;
    if (next_tile < k_tiles) {
      // The ring slot is reused only after all CTA threads finish reading it.
      __syncthreads();
      stage_k_tile(shared_a[slot], shared_b[slot], M, N, K,
                   next_tile * TILE, A, B);
      commit_async_copies();
    }
  }

  const std::size_t row = static_cast<std::size_t>(blockIdx.y) * TILE + ty;
  const std::size_t col = static_cast<std::size_t>(blockIdx.x) * TILE + tx;
  if (row < static_cast<std::size_t>(M) && col < static_cast<std::size_t>(N)) {
    const std::size_t c_index = row * static_cast<std::size_t>(N) + col;
    C[c_index] = alpha * sum + beta * C[c_index];
  }
}

}  // namespace

extern "C" void run(const float *A, const float *B, float *C, float *scratch,
                    int n, int m, int k, float alpha, float beta) {
  (void)scratch;
  if (n <= 0 || m <= 0) {
    return;
  }
  const dim3 block(TILE, TILE);
  const dim3 grid(static_cast<unsigned int>(m / TILE + (m % TILE != 0)),
                  static_cast<unsigned int>(n / TILE + (n % TILE != 0)));
  sgemm_tiled_async<<<grid, block>>>(n, m, k, alpha, A, B, beta, C);
}
