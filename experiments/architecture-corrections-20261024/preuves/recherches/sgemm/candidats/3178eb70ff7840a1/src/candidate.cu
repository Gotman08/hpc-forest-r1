#include <cuda_runtime.h>
#include <stdint.h>

namespace {

constexpr int kBlockX = 32;
constexpr int kBlockY = 8;
constexpr int kTileM = 16;
constexpr int kTileN = 64;
constexpr int kTileK = 32;
constexpr int kThreads = kBlockX * kBlockY;

template <bool Async>
__device__ __forceinline__ void copy_scalar(float *dst, const float *src) {
  if (Async) {
    const unsigned int shared_address =
        static_cast<unsigned int>(__cvta_generic_to_shared(dst));
    asm volatile("cp.async.ca.shared.global [%0], [%1], 4;"
                 :
                 : "r"(shared_address), "l"(src)
                 : "memory");
  } else {
    *dst = *src;
  }
}

template <bool Async>
__device__ __forceinline__ void copy_vector(float *dst, const float *src) {
  if (Async) {
    const unsigned int shared_address =
        static_cast<unsigned int>(__cvta_generic_to_shared(dst));
    asm volatile("cp.async.ca.shared.global [%0], [%1], 16;"
                 :
                 : "r"(shared_address), "l"(src)
                 : "memory");
  } else {
    const float4 values = *reinterpret_cast<const float4 *>(src);
    *reinterpret_cast<float4 *>(dst) = values;
  }
}

template <bool Async>
__device__ __forceinline__ void commit_copies() {
  if (Async) {
    asm volatile("cp.async.commit_group;" ::: "memory");
  }
}

template <bool Async>
__device__ __forceinline__ void wait_for_copies() {
  if (Async) {
    asm volatile("cp.async.wait_group 0;" ::: "memory");
  }
}

__device__ __forceinline__ bool aligned_16(const void *ptr) {
  return (reinterpret_cast<uintptr_t>(ptr) & static_cast<uintptr_t>(15)) == 0;
}

template <bool Async, bool Vectorized>
__device__ __forceinline__ void stage_tile(
    const float *A, const float *B, int M, int N, int K, int row_origin,
    int col_origin, int k_origin, float *shared_a, float *shared_b) {
  const int tid = static_cast<int>(threadIdx.y) * kBlockX +
                  static_cast<int>(threadIdx.x);

  // Each group covers four adjacent K values for one A row.
  constexpr int kAGroups = kTileM * (kTileK / 4);
  for (int group = tid; group < kAGroups; group += kThreads) {
    const int tile_row = group / (kTileK / 4);
    const int group_k = group % (kTileK / 4);
    const int row = row_origin + tile_row;
    const int tile_k = group_k * 4;
    const int k = k_origin + tile_k;
    float *dst = &shared_a[tile_row * kTileK + tile_k];
    const bool base_valid = row < M && k < K;
    const float *src = base_valid
                           ? A + static_cast<unsigned long long>(row) * K + k
                           : A;
    const bool full_valid = row < M && K >= 4 && k <= K - 4;

    if (Vectorized && full_valid && aligned_16(src) && aligned_16(dst)) {
      copy_vector<Async>(dst, src);
    } else {
      for (int j = 0; j < 4; ++j) {
        if (row < M && k + j < K) {
          copy_scalar<Async>(dst + j, src + j);
        } else {
          dst[j] = 0.0f;
        }
      }
    }
  }

  // Each group covers four adjacent columns for one B row.
  constexpr int kBGroups = kTileK * (kTileN / 4);
  for (int group = tid; group < kBGroups; group += kThreads) {
    const int tile_k = group / (kTileN / 4);
    const int group_col = group % (kTileN / 4);
    const int k = k_origin + tile_k;
    const int tile_col = group_col * 4;
    const int col = col_origin + tile_col;
    float *dst = &shared_b[tile_k * kTileN + tile_col];
    const bool base_valid = k < K && col < N;
    const float *src = base_valid
                           ? B + static_cast<unsigned long long>(k) * N + col
                           : B;
    const bool full_valid = k < K && N >= 4 && col <= N - 4;

    if (Vectorized && full_valid && aligned_16(src) && aligned_16(dst)) {
      copy_vector<Async>(dst, src);
    } else {
      for (int j = 0; j < 4; ++j) {
        if (k < K && col + j < N) {
          copy_scalar<Async>(dst + j, src + j);
        } else {
          dst[j] = 0.0f;
        }
      }
    }
  }
}

template <bool Async, bool Vectorized>
__global__ void sgemm_tiled(int M, int N, int K, float alpha, const float *A,
                            const float *B, float beta, float *C) {
  __shared__ __align__(16) float shared_a[2][kTileM * kTileK];
  __shared__ __align__(16) float shared_b[2][kTileK * kTileN];

  const int row_origin = static_cast<int>(blockIdx.y) * kTileM;
  const int col_origin = static_cast<int>(blockIdx.x) * kTileN;
  const int row0 = row_origin + static_cast<int>(threadIdx.y);
  const int row1 = row0 + kBlockY;
  const int col0 = col_origin + static_cast<int>(threadIdx.x);
  const int col1 = col0 + kBlockX;
  const int k_tiles = K > 0 ? K / kTileK + ((K % kTileK) != 0) : 0;

  float acc00 = 0.0f;
  float acc01 = 0.0f;
  float acc10 = 0.0f;
  float acc11 = 0.0f;

  if (k_tiles > 0) {
    stage_tile<Async, Vectorized>(A, B, M, N, K, row_origin, col_origin, 0,
                                  shared_a[0], shared_b[0]);
    commit_copies<Async>();
    wait_for_copies<Async>();
    __syncthreads();

    int current_buffer = 0;
    for (int tile = 0; tile < k_tiles; ++tile) {
      const bool has_next = tile + 1 < k_tiles;
      const int next_buffer = current_buffer ^ 1;
      if (has_next) {
        stage_tile<Async, Vectorized>(
            A, B, M, N, K, row_origin, col_origin, (tile + 1) * kTileK,
            shared_a[next_buffer], shared_b[next_buffer]);
        commit_copies<Async>();
      }

      for (int kk = 0; kk < kTileK; ++kk) {
        const float a0 = shared_a[current_buffer]
                                  [static_cast<int>(threadIdx.y) * kTileK + kk];
        const float a1 = shared_a[current_buffer]
                                  [(static_cast<int>(threadIdx.y) + kBlockY) *
                                       kTileK +
                                   kk];
        const float b0 = shared_b[current_buffer]
                                  [kk * kTileN + static_cast<int>(threadIdx.x)];
        const float b1 = shared_b[current_buffer]
                                  [kk * kTileN + static_cast<int>(threadIdx.x) +
                                   kBlockX];
        acc00 += a0 * b0;
        acc01 += a0 * b1;
        acc10 += a1 * b0;
        acc11 += a1 * b1;
      }

      if (has_next) {
        wait_for_copies<Async>();
        __syncthreads();
        current_buffer = next_buffer;
      }
    }
  }

  if (row0 < M && col0 < N) {
    const unsigned long long offset =
        static_cast<unsigned long long>(row0) * N + col0;
    C[offset] = alpha * acc00 + beta * C[offset];
  }
  if (row0 < M && col1 < N) {
    const unsigned long long offset =
        static_cast<unsigned long long>(row0) * N + col1;
    C[offset] = alpha * acc01 + beta * C[offset];
  }
  if (row1 < M && col0 < N) {
    const unsigned long long offset =
        static_cast<unsigned long long>(row1) * N + col0;
    C[offset] = alpha * acc10 + beta * C[offset];
  }
  if (row1 < M && col1 < N) {
    const unsigned long long offset =
        static_cast<unsigned long long>(row1) * N + col1;
    C[offset] = alpha * acc11 + beta * C[offset];
  }
}

template <bool Async, bool Vectorized>
void launch_sgemm(int M, int N, int K, float alpha, const float *A,
                  const float *B, float beta, float *C) {
  if (M <= 0 || N <= 0) {
    return;
  }

  const dim3 block(kBlockX, kBlockY);
  const dim3 grid(static_cast<unsigned int>((N - 1) / kTileN + 1),
                  static_cast<unsigned int>((M - 1) / kTileM + 1));
  sgemm_tiled<Async, Vectorized><<<grid, block>>>(M, N, K, alpha, A, B, beta,
                                                  C);
}

}  // namespace

extern "C" void run(const float *A, const float *B, float *C, float *scratch,
                     int n, int m, int k, float alpha, float beta) {
  (void)scratch;
  launch_sgemm<true, true>(n, m, k, alpha, A, B, beta, C);
}

// Matched synchronous 16-byte-granularity control.
extern "C" void run_sync(const float *A, const float *B, float *C,
                          float *scratch, int n, int m, int k, float alpha,
                          float beta) {
  (void)scratch;
  launch_sgemm<false, true>(n, m, k, alpha, A, B, beta, C);
}

// Matched 4-byte-granularity pair for isolating the staging load width.
extern "C" void run_scalar(const float *A, const float *B, float *C,
                            float *scratch, int n, int m, int k, float alpha,
                            float beta) {
  (void)scratch;
  launch_sgemm<true, false>(n, m, k, alpha, A, B, beta, C);
}

extern "C" void run_scalar_sync(const float *A, const float *B, float *C,
                                 float *scratch, int n, int m, int k,
                                 float alpha, float beta) {
  (void)scratch;
  launch_sgemm<false, false>(n, m, k, alpha, A, B, beta, C);
}
