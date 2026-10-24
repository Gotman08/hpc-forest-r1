#include <cuda_runtime.h>
/* Copyright (c) 1993-2015, NVIDIA CORPORATION. All rights reserved.
 *
 * Redistribution and use in source and binary forms, with or without
 * modification, are permitted provided that the following conditions
 * are met:
 *  * Redistributions of source code must retain the above copyright
 *    notice, this list of conditions and the following disclaimer.
 *  * Redistributions in binary form must reproduce the above copyright
 *    notice, this list of conditions and the following disclaimer in the
 *    documentation and/or other materials provided with the distribution.
 *  * Neither the name of NVIDIA CORPORATION nor the names of its
 *    contributors may be used to endorse or promote products derived
 *    from this software without specific prior written permission.
 *
 * THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS ``AS IS'' AND ANY
 * EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
 * IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR
 * PURPOSE ARE DISCLAIMED.  IN NO EVENT SHALL THE COPYRIGHT OWNER OR
 * CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL,
 * EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO,
 * PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR
 * PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY
 * OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
 * (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
 * OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
 */

#include <stdio.h>
#include <assert.h>

// Convenience function for checking CUDA runtime API results
// can be wrapped around any runtime API call. No-op in release builds.
inline
cudaError_t checkCuda(cudaError_t result)
{
#if defined(DEBUG) || defined(_DEBUG)
  if (result != cudaSuccess) {
    fprintf(stderr, "CUDA Runtime Error: %s\n", cudaGetErrorString(result));
    assert(result == cudaSuccess);
  }
#endif
  return result;
}

float fx = 1.0f, fy = 1.0f, fz = 1.0f;
const int mx = 64, my = 64, mz = 64;

// Shared-memory tile configurations retained for the parameter setup.
const int sPencils = 4;
const int lPencils = 32;

dim3 grid[3][2], block[3][2];

// Stencil coefficients.
__constant__ float c_ax, c_bx, c_cx, c_dx;
__constant__ float c_ay, c_by, c_cy, c_dy;
__constant__ float c_az, c_bz, c_cz, c_dz;

// Host routine to set constant data.
void setDerivativeParameters()
{
  if ((mx % sPencils != 0) || (my % sPencils != 0) || (mz % sPencils != 0)) {
    printf("'mx', 'my', and 'mz' must be integral multiples of sPencils\n");
    exit(1);
  }

  if ((mx % lPencils != 0) || (my % lPencils != 0)) {
    printf("'mx' and 'my' must be multiples of lPencils\n");
    exit(1);
  }

  float dsinv = mx - 1.f;
  float ax =  4.f / 5.f   * dsinv;
  float bx = -1.f / 5.f   * dsinv;
  float cx =  4.f / 105.f * dsinv;
  float dx = -1.f / 280.f * dsinv;
  checkCuda(cudaMemcpyToSymbol(c_ax, &ax, sizeof(float), 0, cudaMemcpyHostToDevice));
  checkCuda(cudaMemcpyToSymbol(c_bx, &bx, sizeof(float), 0, cudaMemcpyHostToDevice));
  checkCuda(cudaMemcpyToSymbol(c_cx, &cx, sizeof(float), 0, cudaMemcpyHostToDevice));
  checkCuda(cudaMemcpyToSymbol(c_dx, &dx, sizeof(float), 0, cudaMemcpyHostToDevice));

  dsinv = my - 1.f;
  float ay =  4.f / 5.f   * dsinv;
  float by = -1.f / 5.f   * dsinv;
  float cy =  4.f / 105.f * dsinv;
  float dy = -1.f / 280.f * dsinv;
  checkCuda(cudaMemcpyToSymbol(c_ay, &ay, sizeof(float), 0, cudaMemcpyHostToDevice));
  checkCuda(cudaMemcpyToSymbol(c_by, &by, sizeof(float), 0, cudaMemcpyHostToDevice));
  checkCuda(cudaMemcpyToSymbol(c_cy, &cy, sizeof(float), 0, cudaMemcpyHostToDevice));
  checkCuda(cudaMemcpyToSymbol(c_dy, &dy, sizeof(float), 0, cudaMemcpyHostToDevice));

  dsinv = mz - 1.f;
  float az =  4.f / 5.f   * dsinv;
  float bz = -1.f / 5.f   * dsinv;
  float cz =  4.f / 105.f * dsinv;
  float dz = -1.f / 280.f * dsinv;
  checkCuda(cudaMemcpyToSymbol(c_az, &az, sizeof(float), 0, cudaMemcpyHostToDevice));
  checkCuda(cudaMemcpyToSymbol(c_bz, &bz, sizeof(float), 0, cudaMemcpyHostToDevice));
  checkCuda(cudaMemcpyToSymbol(c_cz, &cz, sizeof(float), 0, cudaMemcpyHostToDevice));
  checkCuda(cudaMemcpyToSymbol(c_dz, &dz, sizeof(float), 0, cudaMemcpyHostToDevice));

  grid[0][0]  = dim3(my / sPencils, mz, 1);
  block[0][0] = dim3(mx, sPencils, 1);

  grid[0][1]  = dim3(my / lPencils, mz, 1);
  block[0][1] = dim3(mx, sPencils, 1);

  grid[1][0]  = dim3(mx / sPencils, mz, 1);
  block[1][0] = dim3(sPencils, my, 1);

  grid[1][1]  = dim3(mx / lPencils, mz, 1);
  block[1][1] = dim3(lPencils, my * sPencils / lPencils, 1);

  grid[2][0]  = dim3(mx / sPencils, my, 1);
  block[2][0] = dim3(sPencils, mz, 1);

  grid[2][1]  = dim3(mx / lPencils, my, 1);
  block[2][1] = dim3(lPencils, mz * sPencils / lPencils, 1);
}

constexpr int outputsPerThread = 7;
constexpr int yThreadsPerBlock = 4;

// Apply the supplied period-63 boundary adjustment without folding index 63.
__device__ __forceinline__ int mapYCoordinate(int q)
{
  if (q < 0) return q + 63;
  if (q > 63) return q - 63;
  return q;
}

// Each thread computes a short run of Y outputs from a rolling register window.
// A warp's lanes differ only in X, so each sampled row is accessed contiguously.
__global__ void derivative_y_rolling(const float *f, float *df)
{
  const int i = blockIdx.x * blockDim.x + threadIdx.x;
  const int yGroup = blockIdx.y * blockDim.y + threadIdx.y;
  const int baseY = yGroup * outputsPerThread;
  const int k = blockIdx.z;

  if (i >= mx || k >= mz || baseY >= my) return;

  const int planeOffset = k * mx * my + i;
  float v0 = f[planeOffset + mapYCoordinate(baseY - 4) * mx];
  float v1 = f[planeOffset + mapYCoordinate(baseY - 3) * mx];
  float v2 = f[planeOffset + mapYCoordinate(baseY - 2) * mx];
  float v3 = f[planeOffset + mapYCoordinate(baseY - 1) * mx];
  float v4 = f[planeOffset + mapYCoordinate(baseY) * mx];
  float v5 = f[planeOffset + mapYCoordinate(baseY + 1) * mx];
  float v6 = f[planeOffset + mapYCoordinate(baseY + 2) * mx];
  float v7 = f[planeOffset + mapYCoordinate(baseY + 3) * mx];
  float v8 = f[planeOffset + mapYCoordinate(baseY + 4) * mx];

#pragma unroll
  for (int r = 0; r < outputsPerThread; ++r) {
    const int y = baseY + r;
    if (y < my) {
      const int outIndex = planeOffset + y * mx;
      df[outIndex] =
          (c_ay * (v5 - v3)
         + c_by * (v6 - v2)
         + c_cy * (v7 - v1)
         + c_dy * (v8 - v0));
    }

    if (r + 1 < outputsPerThread && y + 1 < my) {
      v0 = v1;
      v1 = v2;
      v2 = v3;
      v3 = v4;
      v4 = v5;
      v5 = v6;
      v6 = v7;
      v7 = v8;
      v8 = f[planeOffset + mapYCoordinate(y + 5) * mx];
    }
  }
}

extern "C" void run(const float *A, const float *B, float *C, float *scratch,
                    int n, int m, int k, float alpha, float beta)
{
  static bool initialized = false;
  if (!initialized) {
    setDerivativeParameters();
    initialized = true;
  }

  const dim3 blockSize(32, yThreadsPerBlock, 1);
  const int yRowsPerBlock = outputsPerThread * yThreadsPerBlock;
  const dim3 gridSize((mx + blockSize.x - 1) / blockSize.x,
                      (my + yRowsPerBlock - 1) / yRowsPerBlock,
                      mz);
  derivative_y_rolling<<<gridSize, blockSize>>>(A, C);
}
