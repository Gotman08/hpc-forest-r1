#include <cuda_runtime.h>

namespace {
constexpr int BM = 64;
constexpr int BN = 64;
constexpr int BK = 32;
constexpr int THREAD_COLS = 32;
constexpr int THREAD_ROWS = 8;
constexpr int THREADS = THREAD_COLS * THREAD_ROWS;
}

__global__ void sgemm_tiled(int M, int N, int K, float alpha, const float *A,
                            const float *B, float beta, float *C) {
  __shared__ float tileA[BM * BK];
  __shared__ float tileB[BK * BN];

  const int tx = static_cast<int>(threadIdx.x);
  const int ty = static_cast<int>(threadIdx.y);
  const int tid = ty * THREAD_COLS + tx;
  const int blockRow = static_cast<int>(blockIdx.y) * BM;
  const int blockCol = static_cast<int>(blockIdx.x) * BN;

  float accum[8][2] = {};

  for (int k0 = 0; k0 < K; k0 += BK) {
    for (int index = tid; index < BM * BK; index += THREADS) {
      const int row = index / BK;
      const int k = index % BK;
      const int globalRow = blockRow + row;
      const int globalK = k0 + k;
      tileA[index] = (globalRow < M && globalK < K)
                         ? A[static_cast<size_t>(globalRow) * K + globalK]
                         : 0.0f;
    }

    for (int index = tid; index < BK * BN; index += THREADS) {
      const int k = index / BN;
      const int col = index % BN;
      const int globalK = k0 + k;
      const int globalCol = blockCol + col;
      tileB[index] = (globalK < K && globalCol < N)
                         ? B[static_cast<size_t>(globalK) * N + globalCol]
                         : 0.0f;
    }

    __syncthreads();

    for (int kk = 0; kk < BK; ++kk) {
      const int bIndex = kk * BN + tx;
      const float b0 = tileB[bIndex];
      const float b1 = tileB[bIndex + THREAD_COLS];
#pragma unroll
      for (int r = 0; r < 8; ++r) {
        const int aIndex = (ty + r * THREAD_ROWS) * BK + kk;
        const float a = tileA[aIndex];
        accum[r][0] += a * b0;
        accum[r][1] += a * b1;
      }
    }

    __syncthreads();
  }

#pragma unroll
  for (int r = 0; r < 8; ++r) {
    const int row = blockRow + ty + r * THREAD_ROWS;
    const int col0 = blockCol + tx;
    const int col1 = col0 + THREAD_COLS;
    if (row < M) {
      if (col0 < N) {
        const size_t index = static_cast<size_t>(row) * N + col0;
        if (beta == 0.0f) {
          C[index] = alpha * accum[r][0];
        } else {
          C[index] = alpha * accum[r][0] + beta * C[index];
        }
      }
      if (col1 < N) {
        const size_t index = static_cast<size_t>(row) * N + col1;
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
  if (n == 0 || m == 0) {
    return;
  }

  const dim3 grid(static_cast<unsigned int>((m - 1) / BN + 1),
                  static_cast<unsigned int>((n - 1) / BM + 1));
  const dim3 block(THREAD_COLS, THREAD_ROWS);
  sgemm_tiled<<<grid, block>>>(n, m, k, alpha, A, B, beta, C);
}
