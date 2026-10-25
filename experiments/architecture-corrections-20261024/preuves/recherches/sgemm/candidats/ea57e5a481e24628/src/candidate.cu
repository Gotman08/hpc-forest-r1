#include <cuda_runtime.h>

#include <cstddef>

__global__ void sgemm_tiled(int M, int N, int K, float alpha, const float *A,
                            const float *B, float beta, float *C) {
  constexpr int BM = 64;
  constexpr int BN = 64;
  constexpr int BK = 64;

  __shared__ float tileA[BM][BK];
  __shared__ float tileB[BK][BN];

  const int tid = static_cast<int>(threadIdx.x);
  const int laneCol = tid & 31;
  const int rowGroup = tid >> 5;
  const int baseM = static_cast<int>(blockIdx.y) * BM;
  const int baseN = static_cast<int>(blockIdx.x) * BN;
  float accum[8][2] = {};

  for (int kBase = 0; kBase < K;) {
    const int validK = (K - kBase < BK) ? (K - kBase) : BK;

    for (int idx = tid; idx < BM * BK; idx += blockDim.x) {
      const int rowInTile = idx / BK;
      const int kInTile = idx % BK;
      const long long row = static_cast<long long>(baseM) + rowInTile;
      if (row < M && kInTile < validK) {
        const int globalK = kBase + kInTile;
        tileA[rowInTile][kInTile] =
            A[static_cast<std::size_t>(row) * K + globalK];
      } else {
        tileA[rowInTile][kInTile] = 0.0f;
      }
    }

    for (int idx = tid; idx < BK * BN; idx += blockDim.x) {
      const int kInTile = idx / BN;
      const int colInTile = idx % BN;
      const long long col = static_cast<long long>(baseN) + colInTile;
      if (col < N && kInTile < validK) {
        const int globalK = kBase + kInTile;
        tileB[kInTile][colInTile] =
            B[static_cast<std::size_t>(globalK) * N + col];
      } else {
        tileB[kInTile][colInTile] = 0.0f;
      }
    }

    __syncthreads();

#pragma unroll 4
    for (int kInTile = 0; kInTile < BK; ++kInTile) {
      const float b0 = tileB[kInTile][laneCol];
      const float b1 = tileB[kInTile][laneCol + 32];
#pragma unroll
      for (int r = 0; r < 8; ++r) {
        const float a = tileA[rowGroup * 8 + r][kInTile];
        accum[r][0] = fmaf(a, b0, accum[r][0]);
        accum[r][1] = fmaf(a, b1, accum[r][1]);
      }
    }

    __syncthreads();
    kBase += validK;
  }

  const int col0 = baseN + laneCol;
  const int col1 = col0 + 32;
#pragma unroll
  for (int r = 0; r < 8; ++r) {
    const long long row = static_cast<long long>(baseM) + rowGroup * 8 + r;
    if (row < M) {
      if (col0 < N) {
        const std::size_t index = static_cast<std::size_t>(row) * N + col0;
        const float product = alpha * accum[r][0];
        C[index] = (beta == 0.0f) ? product : product + beta * C[index];
      }
      if (col1 < N) {
        const std::size_t index = static_cast<std::size_t>(row) * N + col1;
        const float product = alpha * accum[r][1];
        C[index] = (beta == 0.0f) ? product : product + beta * C[index];
      }
    }
  }
}

extern "C" void run(const float *A, const float *B, float *C, float *scratch,
                    int n, int m, int k, float alpha, float beta) {
  (void)scratch;
  if (n <= 0 || m <= 0) {
    return;
  }
  const int blocksM = n / 64 + (n % 64 != 0);
  const int blocksN = m / 64 + (m % 64 != 0);
  sgemm_tiled<<<dim3(blocksN, blocksM), dim3(256, 1, 1)>>>(
      n, m, k, alpha, A, B, beta, C);
}
