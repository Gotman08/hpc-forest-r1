#include <cstddef>
#include <cuda_runtime.h>

static constexpr int TILE = 16;

// Synchronous staging control: (ty, tx) computes C[row, col]. The same
// thread mapping cooperatively loads one A and one B element per K stage.
__global__ void sgemm_tiled_sync(int M, int N, int K, float alpha,
                                 const float *A, const float *B, float beta,
                                 float *C) {
  const int tx = threadIdx.x;
  const int ty = threadIdx.y;
  const int row = blockIdx.y * TILE + ty;
  const int col = blockIdx.x * TILE + tx;

  __shared__ float staged_a[TILE][TILE];
  __shared__ float staged_b[TILE][TILE];
  float sum = 0.0f;

  for (int k0 = 0; k0 < K; k0 += TILE) {
    const int a_col = k0 + tx;
    const int b_row = k0 + ty;
    staged_a[ty][tx] = (row < M && a_col < K)
                            ? A[static_cast<size_t>(row) * K + a_col]
                            : 0.0f;
    staged_b[ty][tx] = (b_row < K && col < N)
                            ? B[static_cast<size_t>(b_row) * N + col]
                            : 0.0f;

    __syncthreads();
    for (int kk = 0; kk < TILE; ++kk) {
      sum += staged_a[ty][kk] * staged_b[kk][tx];
    }
    __syncthreads();
  }

  if (row < M && col < N) {
    const size_t c_index = static_cast<size_t>(row) * N + col;
    C[c_index] = alpha * sum + beta * C[c_index];
  }
}

extern "C" void run(const float *A, const float *B, float *C, float *scratch,
                    int n, int m, int k, float alpha, float beta) {
  (void)scratch;
  if (n <= 0 || m <= 0) {
    return;
  }
  const dim3 block(TILE, TILE);
  const dim3 grid(static_cast<unsigned int>(m / TILE + (m % TILE != 0)),
                  static_cast<unsigned int>(n / TILE + (n % TILE != 0)));
  sgemm_tiled_sync<<<grid, block>>>(n, m, k, alpha, A, B, beta, C);
}
