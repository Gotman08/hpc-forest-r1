#include <cuda_runtime.h>
#include <stddef.h>

namespace {
constexpr int kBlockM = 64;
constexpr int kBlockN = 32;
constexpr int kBlockK = 16;
constexpr int kThreadsX = 32;
constexpr int kThreadsY = 8;
constexpr int kRowsPerThread = kBlockM / kThreadsY;

__global__ void sgemm_tiled(int M, int N, int K, float alpha,
                            const float* A, const float* B, float beta,
                            float* C) {
  __shared__ float sharedA[kBlockM * kBlockK];
  __shared__ float sharedB[kBlockK * kBlockN];

  const int tx = threadIdx.x;
  const int ty = threadIdx.y;
  const int tid = ty * blockDim.x + tx;
  const int threadCount = blockDim.x * blockDim.y;
  const int rowBase = static_cast<int>(blockIdx.y) * kBlockM + ty;
  const int col = static_cast<int>(blockIdx.x) * kBlockN + tx;

  float accum[kRowsPerThread] = {0.0f, 0.0f, 0.0f, 0.0f,
                                 0.0f, 0.0f, 0.0f, 0.0f};

  for (int kBase = 0; kBase < K; kBase += kBlockK) {
    for (int idx = tid; idx < kBlockM * kBlockK; idx += threadCount) {
      const int tileRow = idx / kBlockK;
      const int tileK = idx % kBlockK;
      const int globalRow = static_cast<int>(blockIdx.y) * kBlockM + tileRow;
      const int globalK = kBase + tileK;
      float value = 0.0f;
      if (globalRow < M && globalK < K) {
        const size_t offset = static_cast<size_t>(globalRow) * K + globalK;
        value = A[offset];
      }
      sharedA[idx] = value;
    }

    for (int idx = tid; idx < kBlockK * kBlockN; idx += threadCount) {
      const int tileK = idx / kBlockN;
      const int tileCol = idx % kBlockN;
      const int globalK = kBase + tileK;
      const int globalCol = static_cast<int>(blockIdx.x) * kBlockN + tileCol;
      float value = 0.0f;
      if (globalK < K && globalCol < N) {
        const size_t offset = static_cast<size_t>(globalK) * N + globalCol;
        value = B[offset];
      }
      sharedB[idx] = value;
    }

    __syncthreads();

    #pragma unroll
    for (int p = 0; p < kBlockK; ++p) {
      const float b = sharedB[p * kBlockN + tx];
      #pragma unroll
      for (int r = 0; r < kRowsPerThread; ++r) {
        const int tileRow = ty + r * kThreadsY;
        const float a = sharedA[tileRow * kBlockK + p];
        accum[r] = fmaf(a, b, accum[r]);
      }
    }

    __syncthreads();
  }

  #pragma unroll
  for (int r = 0; r < kRowsPerThread; ++r) {
    const int row = rowBase + r * kThreadsY;
    if (row < M && col < N) {
      const size_t offset = static_cast<size_t>(row) * N + col;
      float value = alpha * accum[r];
      if (beta != 0.0f) {
        value += beta * C[offset];
      }
      C[offset] = value;
    }
  }
}
}  // namespace

extern "C" void run(const float* A, const float* B, float* C, float* scratch,
                    int n, int m, int k, float alpha, float beta) {
  (void)scratch;
  if (n <= 0 || m <= 0) {
    return;
  }

  const dim3 block(kThreadsX, kThreadsY);
  const dim3 grid(1 + (m - 1) / kBlockN, 1 + (n - 1) / kBlockM);
  sgemm_tiled<<<grid, block>>>(n, m, k, alpha, A, B, beta, C);
}
