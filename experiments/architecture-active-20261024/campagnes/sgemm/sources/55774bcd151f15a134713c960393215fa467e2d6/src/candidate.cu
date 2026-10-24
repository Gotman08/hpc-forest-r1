#include <cstddef>
#include <cuda_runtime.h>

__global__ void sgemm_register_blocked(int M, int N, int K, float alpha,
                                       const float *A, const float *B,
                                       float beta, float *C) {
  const size_t m_size = static_cast<size_t>(M);
  const size_t n_size = static_cast<size_t>(N);
  const size_t k_size = static_cast<size_t>(K);
  const size_t col0 = static_cast<size_t>(blockIdx.x) * 32u +
                      static_cast<size_t>(threadIdx.x) * 2u;
  const size_t col1 = col0 + 1u;
  const size_t row0 = static_cast<size_t>(blockIdx.y) * 32u +
                      static_cast<size_t>(threadIdx.y) * 4u;
  const size_t row1 = row0 + 1u;
  const size_t row2 = row0 + 2u;
  const size_t row3 = row0 + 3u;

  if (col0 < n_size && row0 < m_size) {
    float acc00 = 0.0f;
    float acc01 = 0.0f;
    float acc10 = 0.0f;
    float acc11 = 0.0f;
    float acc20 = 0.0f;
    float acc21 = 0.0f;
    float acc30 = 0.0f;
    float acc31 = 0.0f;

    for (int p = 0; p < K; ++p) {
      const size_t a_base = static_cast<size_t>(p);
      const size_t b_base = static_cast<size_t>(p) * n_size;
      const float a0 = A[row0 * k_size + a_base];
      const float a1 = row1 < m_size ? A[row1 * k_size + a_base] : 0.0f;
      const float a2 = row2 < m_size ? A[row2 * k_size + a_base] : 0.0f;
      const float a3 = row3 < m_size ? A[row3 * k_size + a_base] : 0.0f;
      const float b0 = B[b_base + col0];
      const float b1 = col1 < n_size ? B[b_base + col1] : 0.0f;

      acc00 += a0 * b0;
      acc01 += a0 * b1;
      acc10 += a1 * b0;
      acc11 += a1 * b1;
      acc20 += a2 * b0;
      acc21 += a2 * b1;
      acc30 += a3 * b0;
      acc31 += a3 * b1;
    }

    size_t idx = row0 * n_size + col0;
    C[idx] = alpha * acc00 + beta * C[idx];
    if (col1 < n_size) {
      idx = row0 * n_size + col1;
      C[idx] = alpha * acc01 + beta * C[idx];
    }
    if (row1 < m_size) {
      idx = row1 * n_size + col0;
      C[idx] = alpha * acc10 + beta * C[idx];
      if (col1 < n_size) {
        idx = row1 * n_size + col1;
        C[idx] = alpha * acc11 + beta * C[idx];
      }
    }
    if (row2 < m_size) {
      idx = row2 * n_size + col0;
      C[idx] = alpha * acc20 + beta * C[idx];
      if (col1 < n_size) {
        idx = row2 * n_size + col1;
        C[idx] = alpha * acc21 + beta * C[idx];
      }
    }
    if (row3 < m_size) {
      idx = row3 * n_size + col0;
      C[idx] = alpha * acc30 + beta * C[idx];
      if (col1 < n_size) {
        idx = row3 * n_size + col1;
        C[idx] = alpha * acc31 + beta * C[idx];
      }
    }
  }
}

extern "C" void run(const float *A, const float *B, float *C, float *scratch,
                    int n, int m, int k, float alpha, float beta) {
  if (n <= 0 || m <= 0) return;
  const int blocks_x = m / 32 + (m % 32 != 0);
  const int blocks_y = n / 32 + (n % 32 != 0);
  sgemm_register_blocked<<<dim3(blocks_x, blocks_y), dim3(16, 8)>>>(
      n, m, k, alpha, A, B, beta, C);
}
