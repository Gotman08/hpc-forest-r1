#include <cuda_runtime.h>
#include <stddef.h>

__global__ void sgemm_tiled_8x32_k16(int M, int N, int K, float alpha,
                                     const float *A, const float *B,
                                     float beta, float *C) {
  __shared__ float aTile[8][16];
  __shared__ float bTile[16][32];

  const int row = static_cast<int>(blockIdx.y) * 8 +
                  static_cast<int>(threadIdx.y);
  const int col = static_cast<int>(blockIdx.x) * 32 +
                  static_cast<int>(threadIdx.x);
  float acc = 0.0f;

  for (int kBase = 0; kBase < K;) {
    if (threadIdx.x < 16) {
      const int aK = kBase + static_cast<int>(threadIdx.x);
      aTile[threadIdx.y][threadIdx.x] =
          (row < M && aK < K)
              ? A[static_cast<size_t>(row) * static_cast<size_t>(K) +
                  static_cast<size_t>(aK)]
              : 0.0f;
    }

    const int bK0 = kBase + static_cast<int>(threadIdx.y);
    const int bK1 = bK0 + 8;
    bTile[threadIdx.y][threadIdx.x] =
        (bK0 < K && col < N)
            ? B[static_cast<size_t>(bK0) * static_cast<size_t>(N) +
                static_cast<size_t>(col)]
            : 0.0f;
    bTile[threadIdx.y + 8][threadIdx.x] =
        (bK1 < K && col < N)
            ? B[static_cast<size_t>(bK1) * static_cast<size_t>(N) +
                static_cast<size_t>(col)]
            : 0.0f;

    __syncthreads();
    #pragma unroll
    for (int kk = 0; kk < 16; ++kk) {
      acc += aTile[threadIdx.y][kk] * bTile[kk][threadIdx.x];
    }
    __syncthreads();

    if (K - kBase <= 16) {
      break;
    }
    kBase += 16;
  }

  if (row < M && col < N) {
    const size_t idx = static_cast<size_t>(row) * static_cast<size_t>(N) +
                       static_cast<size_t>(col);
    C[idx] = alpha * acc + beta * C[idx];
  }
}

extern "C" void run(const float *A, const float *B, float *C, float *scratch,
                    int n, int m, int k, float alpha, float beta) {
  (void)scratch;
  if (n == 0 || m == 0) {
    return;
  }
  const int gridCols = m / 32 + (m % 32 != 0);
  const int gridRows = n / 8 + (n % 8 != 0);
  sgemm_tiled_8x32_k16<<<dim3(gridCols, gridRows), dim3(32, 8)>>>(
      n, m, k, alpha, A, B, beta, C);
}
