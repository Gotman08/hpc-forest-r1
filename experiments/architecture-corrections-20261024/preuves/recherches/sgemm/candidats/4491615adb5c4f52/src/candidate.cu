#include <cuda_runtime.h>
#include <stddef.h>

/* Each warp computes four rows across 32 contiguous output columns. */
__global__ void sgemm_warp_register(int M, int N, int K, float alpha,
                                    const float *A, const float *B,
                                    float beta, float *C) {
  const int lane = threadIdx.x;
  const size_t row_base = static_cast<size_t>(blockIdx.y) * 16u +
                          static_cast<size_t>(threadIdx.y) * 4u;
  const size_t col = static_cast<size_t>(blockIdx.x) * 32u +
                     static_cast<size_t>(lane);
  const size_t m_size = static_cast<size_t>(M);
  const size_t n_size = static_cast<size_t>(N);
  constexpr unsigned int full_warp_mask = 0xffffffffu;

  float acc0 = 0.0f;
  float acc1 = 0.0f;
  float acc2 = 0.0f;
  float acc3 = 0.0f;

  for (int kk = 0; kk < K; ++kk) {
    const size_t b_index = static_cast<size_t>(kk) * n_size + col;
    const float b = col < n_size ? B[b_index] : 0.0f;

    float a0 = lane == 0 && row_base < m_size
                   ? A[row_base * static_cast<size_t>(K) +
                       static_cast<size_t>(kk)]
                   : 0.0f;
    float a1 = lane == 0 && row_base + 1u < m_size
                   ? A[(row_base + 1u) * static_cast<size_t>(K) +
                       static_cast<size_t>(kk)]
                   : 0.0f;
    float a2 = lane == 0 && row_base + 2u < m_size
                   ? A[(row_base + 2u) * static_cast<size_t>(K) +
                       static_cast<size_t>(kk)]
                   : 0.0f;
    float a3 = lane == 0 && row_base + 3u < m_size
                   ? A[(row_base + 3u) * static_cast<size_t>(K) +
                       static_cast<size_t>(kk)]
                   : 0.0f;

    a0 = __shfl_sync(full_warp_mask, a0, 0);
    a1 = __shfl_sync(full_warp_mask, a1, 0);
    a2 = __shfl_sync(full_warp_mask, a2, 0);
    a3 = __shfl_sync(full_warp_mask, a3, 0);

    acc0 = __fmaf_rn(a0, b, acc0);
    acc1 = __fmaf_rn(a1, b, acc1);
    acc2 = __fmaf_rn(a2, b, acc2);
    acc3 = __fmaf_rn(a3, b, acc3);
  }

  if (col < n_size) {
    if (row_base < m_size) {
      const size_t index = row_base * n_size + col;
      C[index] = alpha * acc0 + beta * C[index];
    }
    if (row_base + 1u < m_size) {
      const size_t index = (row_base + 1u) * n_size + col;
      C[index] = alpha * acc1 + beta * C[index];
    }
    if (row_base + 2u < m_size) {
      const size_t index = (row_base + 2u) * n_size + col;
      C[index] = alpha * acc2 + beta * C[index];
    }
    if (row_base + 3u < m_size) {
      const size_t index = (row_base + 3u) * n_size + col;
      C[index] = alpha * acc3 + beta * C[index];
    }
  }
}

extern "C" void run(const float *A, const float *B, float *C, float *scratch,
                    int n, int m, int k, float alpha, float beta) {
  (void)scratch;
  if (n <= 0 || m <= 0) {
    return;
  }

  const unsigned int grid_x = static_cast<unsigned int>(m / 32 + (m % 32 != 0));
  const unsigned int grid_y = static_cast<unsigned int>(n / 16 + (n % 16 != 0));
  sgemm_warp_register<<<dim3(grid_x, grid_y), dim3(32, 4)>>>(
      n, m, k, alpha, A, B, beta, C);
}
