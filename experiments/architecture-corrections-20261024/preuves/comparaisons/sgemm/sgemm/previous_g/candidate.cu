#include <cstddef>
#include <cuda_runtime.h>

__global__ void sgemm_register_blocked(int M, int N, int K, float alpha,
                                       const float *A, const float *B,
                                       float beta, float *C) {
  // Each thread computes two rows by four column stripes.
  const size_t row0 = static_cast<size_t>(blockIdx.y) * 8 + threadIdx.y;
  const size_t row1 = row0 + 4;
  const size_t col0 = static_cast<size_t>(blockIdx.x) * 128 + threadIdx.x;
  const size_t col1 = col0 + 32;
  const size_t col2 = col0 + 64;
  const size_t col3 = col0 + 96;

  if (row0 >= static_cast<size_t>(N) || col0 >= static_cast<size_t>(M)) return;

  float even00 = 0.0f;
  float even01 = 0.0f;
  float even02 = 0.0f;
  float even03 = 0.0f;
  float even10 = 0.0f;
  float even11 = 0.0f;
  float even12 = 0.0f;
  float even13 = 0.0f;
  float odd00 = 0.0f;
  float odd01 = 0.0f;
  float odd02 = 0.0f;
  float odd03 = 0.0f;
  float odd10 = 0.0f;
  float odd11 = 0.0f;
  float odd12 = 0.0f;
  float odd13 = 0.0f;

  // Accumulate alternating K terms independently to shorten each dependency chain.
  for (int p = 0; p < K;) {
    const size_t a_col = static_cast<size_t>(p);
    const size_t b_row = static_cast<size_t>(p) * static_cast<size_t>(M);
    const float a0 = A[row0 * static_cast<size_t>(K) + a_col];
    const float a1 = row1 < static_cast<size_t>(N)
                         ? A[row1 * static_cast<size_t>(K) + a_col]
                         : 0.0f;
    const float b0 = B[b_row + col0];
    even00 += a0 * b0;
    even10 += a1 * b0;
    if (col1 < static_cast<size_t>(M)) {
      const float b1 = B[b_row + col1];
      even01 += a0 * b1;
      even11 += a1 * b1;
    }
    if (col2 < static_cast<size_t>(M)) {
      const float b2 = B[b_row + col2];
      even02 += a0 * b2;
      even12 += a1 * b2;
    }
    if (col3 < static_cast<size_t>(M)) {
      const float b3 = B[b_row + col3];
      even03 += a0 * b3;
      even13 += a1 * b3;
    }

    if (p < K - 1) {
      const int p_odd = p + 1;
      const size_t odd_col = static_cast<size_t>(p_odd);
      const size_t odd_b_row = odd_col * static_cast<size_t>(M);
      const float odd_a0 = A[row0 * static_cast<size_t>(K) + odd_col];
      const float odd_a1 = row1 < static_cast<size_t>(N)
                               ? A[row1 * static_cast<size_t>(K) + odd_col]
                               : 0.0f;
      const float odd_b0 = B[odd_b_row + col0];
      odd00 += odd_a0 * odd_b0;
      odd10 += odd_a1 * odd_b0;
      if (col1 < static_cast<size_t>(M)) {
        const float odd_b1 = B[odd_b_row + col1];
        odd01 += odd_a0 * odd_b1;
        odd11 += odd_a1 * odd_b1;
      }
      if (col2 < static_cast<size_t>(M)) {
        const float odd_b2 = B[odd_b_row + col2];
        odd02 += odd_a0 * odd_b2;
        odd12 += odd_a1 * odd_b2;
      }
      if (col3 < static_cast<size_t>(M)) {
        const float odd_b3 = B[odd_b_row + col3];
        odd03 += odd_a0 * odd_b3;
        odd13 += odd_a1 * odd_b3;
      }
    }

    if (K - p <= 2) break;
    p += 2;
  }

  const size_t c_row0 = row0 * static_cast<size_t>(M);
  C[c_row0 + col0] = alpha * (even00 + odd00) + beta * C[c_row0 + col0];
  if (col1 < static_cast<size_t>(M))
    C[c_row0 + col1] = alpha * (even01 + odd01) + beta * C[c_row0 + col1];
  if (col2 < static_cast<size_t>(M))
    C[c_row0 + col2] = alpha * (even02 + odd02) + beta * C[c_row0 + col2];
  if (col3 < static_cast<size_t>(M))
    C[c_row0 + col3] = alpha * (even03 + odd03) + beta * C[c_row0 + col3];

  if (row1 < static_cast<size_t>(N)) {
    const size_t c_row1 = row1 * static_cast<size_t>(M);
    C[c_row1 + col0] = alpha * (even10 + odd10) + beta * C[c_row1 + col0];
    if (col1 < static_cast<size_t>(M))
      C[c_row1 + col1] = alpha * (even11 + odd11) + beta * C[c_row1 + col1];
    if (col2 < static_cast<size_t>(M))
      C[c_row1 + col2] = alpha * (even12 + odd12) + beta * C[c_row1 + col2];
    if (col3 < static_cast<size_t>(M))
      C[c_row1 + col3] = alpha * (even13 + odd13) + beta * C[c_row1 + col3];
  }
}

extern "C" void run(const float *A, const float *B, float *C, float *scratch,
                    int n, int m, int k, float alpha, float beta) {
  if (n <= 0 || m <= 0) return;
  const int blocks_x = m / 128 + (m % 128 != 0);
  const int blocks_y = n / 8 + (n % 8 != 0);
  sgemm_register_blocked<<<dim3(blocks_x, blocks_y), dim3(32, 4)>>>(
      n, m, k, alpha, A, B, beta, C);
}
