#include <cuda_runtime.h>
#include <stddef.h>

__global__ void sgemm_tiled_32x16(int M, int N, int K, float alpha,
                                  const float *A, const float *B, float beta,
                                  float *C) {
  __shared__ float aTile[32][16];
  __shared__ float bTile[16][16];

  const int row = static_cast<int>(blockIdx.y) * 32 + threadIdx.y;
  const int col = static_cast<int>(blockIdx.x) * 16 + threadIdx.x;
  const int tid = threadIdx.y * 16 + threadIdx.x;
  float acc = 0.0f;

  for (int kBase = 0; kBase < K;) {
    const int aK = kBase + threadIdx.x;
    aTile[threadIdx.y][threadIdx.x] =
        (row < M && aK < K)
            ? A[static_cast<size_t>(row) * static_cast<size_t>(K) +
                static_cast<size_t>(aK)]
            : 0.0f;

    if (tid < 16 * 16) {
      const int bK = kBase + tid / 16;
      const int bCol = tid % 16;
      bTile[tid / 16][bCol] =
          (bK < K && bCol < N)
              ? B[static_cast<size_t>(bK) * static_cast<size_t>(N) +
                  static_cast<size_t>(bCol)]
              : 0.0f;
    }

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
  const int gridCols = m / 16 + (m % 16 != 0);
  const int gridRows = n / 32 + (n % 32 != 0);
  sgemm_tiled_32x16<<<dim3(gridCols, gridRows), dim3(16, 32)>>>(
      n, m, k, alpha, A, B, beta, C);
}
