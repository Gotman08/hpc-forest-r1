#include <cuda_runtime.h>
#include <stddef.h>

/* Each warp covers four rows and two 32-column segments. */
__global__ void sgemm_warp_pair_columns(int M, int N, int K, float alpha,
                                        const float *A, const float *B,
                                        float beta, float *C) {
  const int lane = threadIdx.x;
  const size_t row_base = static_cast<size_t>(blockIdx.y) * 16u +
                          static_cast<size_t>(threadIdx.y) * 4u;
  const size_t col0 = static_cast<size_t>(blockIdx.x) * 64u +
                      static_cast<size_t>(lane);
  const size_t col1 = col0 + 32u;
  const size_t m_size = static_cast<size_t>(M);
  const size_t n_size = static_cast<size_t>(N);
  constexpr unsigned int full_warp_mask = 0xffffffffu;

  float acc00 = 0.0f, acc01 = 0.0f;
  float acc10 = 0.0f, acc11 = 0.0f;
  float acc20 = 0.0f, acc21 = 0.0f;
  float acc30 = 0.0f, acc31 = 0.0f;

  for (int kk = 0; kk < K; ++kk) {
    const size_t k_offset = static_cast<size_t>(kk) * n_size;
    const float b0 = col0 < n_size ? B[k_offset + col0] : 0.0f;
    const float b1 = col1 < n_size ? B[k_offset + col1] : 0.0f;

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

    acc00 = __fmaf_rn(a0, b0, acc00);
    acc01 = __fmaf_rn(a0, b1, acc01);
    acc10 = __fmaf_rn(a1, b0, acc10);
    acc11 = __fmaf_rn(a1, b1, acc11);
    acc20 = __fmaf_rn(a2, b0, acc20);
    acc21 = __fmaf_rn(a2, b1, acc21);
    acc30 = __fmaf_rn(a3, b0, acc30);
    acc31 = __fmaf_rn(a3, b1, acc31);
  }

  if (col0 < n_size) {
    if (row_base < m_size) {
      const size_t index = row_base * n_size + col0;
      C[index] = alpha * acc00 + beta * C[index];
    }
    if (row_base + 1u < m_size) {
      const size_t index = (row_base + 1u) * n_size + col0;
      C[index] = alpha * acc10 + beta * C[index];
    }
    if (row_base + 2u < m_size) {
      const size_t index = (row_base + 2u) * n_size + col0;
      C[index] = alpha * acc20 + beta * C[index];
    }
    if (row_base + 3u < m_size) {
      const size_t index = (row_base + 3u) * n_size + col0;
      C[index] = alpha * acc30 + beta * C[index];
    }
  }
  if (col1 < n_size) {
    if (row_base < m_size) {
      const size_t index = row_base * n_size + col1;
      C[index] = alpha * acc01 + beta * C[index];
    }
    if (row_base + 1u < m_size) {
      const size_t index = (row_base + 1u) * n_size + col1;
      C[index] = alpha * acc11 + beta * C[index];
    }
    if (row_base + 2u < m_size) {
      const size_t index = (row_base + 2u) * n_size + col1;
      C[index] = alpha * acc21 + beta * C[index];
    }
    if (row_base + 3u < m_size) {
      const size_t index = (row_base + 3u) * n_size + col1;
      C[index] = alpha * acc31 + beta * C[index];
    }
  }
}

extern "C" void run(const float *A, const float *B, float *C, float *scratch,
                    int n, int m, int k, float alpha, float beta) {
  (void)scratch;
  if (n <= 0 || m <= 0) {
    return;
  }

  const unsigned int grid_x = static_cast<unsigned int>(m / 64 + (m % 64 != 0));
  const unsigned int grid_y = static_cast<unsigned int>(n / 16 + (n % 16 != 0));
  sgemm_warp_pair_columns<<<dim3(grid_x, grid_y), dim3(32, 4)>>>(
      n, m, k, alpha, A, B, beta, C);
}
