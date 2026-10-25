#include <cuda_runtime.h>
#include <stddef.h>

/* Each warp computes eight rows across 32 contiguous output columns. */
__global__ void sgemm_warp_register(int M, int N, int K, float alpha,
                                    const float *A, const float *B,
                                    float beta, float *C) {
  const int lane = threadIdx.x;
  const size_t row_base = static_cast<size_t>(blockIdx.y) * 32u +
                          static_cast<size_t>(threadIdx.y) * 8u;
  const size_t col = static_cast<size_t>(blockIdx.x) * 32u +
                     static_cast<size_t>(lane);
  const size_t m_size = static_cast<size_t>(M);
  const size_t n_size = static_cast<size_t>(N);
  constexpr unsigned int full_warp_mask = 0xffffffffu;

  float acc0 = 0.0f;
  float acc1 = 0.0f;
  float acc2 = 0.0f;
  float acc3 = 0.0f;
  float acc4 = 0.0f;
  float acc5 = 0.0f;
  float acc6 = 0.0f;
  float acc7 = 0.0f;

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
    float a4 = lane == 0 && row_base + 4u < m_size
                   ? A[(row_base + 4u) * static_cast<size_t>(K) +
                       static_cast<size_t>(kk)]
                   : 0.0f;
    float a5 = lane == 0 && row_base + 5u < m_size
                   ? A[(row_base + 5u) * static_cast<size_t>(K) +
                       static_cast<size_t>(kk)]
                   : 0.0f;
    float a6 = lane == 0 && row_base + 6u < m_size
                   ? A[(row_base + 6u) * static_cast<size_t>(K) +
                       static_cast<size_t>(kk)]
                   : 0.0f;
    float a7 = lane == 0 && row_base + 7u < m_size
                   ? A[(row_base + 7u) * static_cast<size_t>(K) +
                       static_cast<size_t>(kk)]
                   : 0.0f;

    a0 = __shfl_sync(full_warp_mask, a0, 0);
    a1 = __shfl_sync(full_warp_mask, a1, 0);
    a2 = __shfl_sync(full_warp_mask, a2, 0);
    a3 = __shfl_sync(full_warp_mask, a3, 0);
    a4 = __shfl_sync(full_warp_mask, a4, 0);
    a5 = __shfl_sync(full_warp_mask, a5, 0);
    a6 = __shfl_sync(full_warp_mask, a6, 0);
    a7 = __shfl_sync(full_warp_mask, a7, 0);

    acc0 = __fmaf_rn(a0, b, acc0);
    acc1 = __fmaf_rn(a1, b, acc1);
    acc2 = __fmaf_rn(a2, b, acc2);
    acc3 = __fmaf_rn(a3, b, acc3);
    acc4 = __fmaf_rn(a4, b, acc4);
    acc5 = __fmaf_rn(a5, b, acc5);
    acc6 = __fmaf_rn(a6, b, acc6);
    acc7 = __fmaf_rn(a7, b, acc7);
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
    if (row_base + 4u < m_size) {
      const size_t index = (row_base + 4u) * n_size + col;
      C[index] = alpha * acc4 + beta * C[index];
    }
    if (row_base + 5u < m_size) {
      const size_t index = (row_base + 5u) * n_size + col;
      C[index] = alpha * acc5 + beta * C[index];
    }
    if (row_base + 6u < m_size) {
      const size_t index = (row_base + 6u) * n_size + col;
      C[index] = alpha * acc6 + beta * C[index];
    }
    if (row_base + 7u < m_size) {
      const size_t index = (row_base + 7u) * n_size + col;
      C[index] = alpha * acc7 + beta * C[index];
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
  const unsigned int grid_y = static_cast<unsigned int>(n / 32 + (n % 32 != 0));
  sgemm_warp_register<<<dim3(grid_x, grid_y), dim3(32, 4)>>>(
      n, m, k, alpha, A, B, beta, C);
}
