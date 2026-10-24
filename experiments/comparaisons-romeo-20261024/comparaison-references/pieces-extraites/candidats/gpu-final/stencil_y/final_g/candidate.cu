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
  
// shared memory tiles will be m*-by-*Pencils
// sPencils is used when each thread calculates the derivative at one point
// lPencils is used for coalescing in y and z where each thread has to 
//     calculate the derivative at mutiple points
const int sPencils = 4;  // small # pencils
const int lPencils = 32; // large # pencils
  
dim3 grid[3][2], block[3][2];

// stencil coefficients
__constant__ float c_ax, c_bx, c_cx, c_dx;
__constant__ float c_ay, c_by, c_cy, c_dy;
__constant__ float c_az, c_bz, c_cz, c_dz;
 
// host routine to set constant data
void setDerivativeParameters()
{
  // check to make sure dimensions are integral multiples of sPencils
  if ((mx % sPencils != 0) || (my %sPencils != 0) || (mz %sPencils != 0)) {
    printf("'mx', 'my', and 'mz' must be integral multiples of sPencils\n");
    exit(1);
  }
  
  if ((mx % lPencils != 0) || (my % lPencils != 0)) {
    printf("'mx' and 'my' must be multiples of lPencils\n");
    exit(1);
  }

  // stencil weights (for unit length problem)
  float dsinv = mx-1.f;
  
  float ax =  4.f / 5.f   * dsinv;
  float bx = -1.f / 5.f   * dsinv;
  float cx =  4.f / 105.f * dsinv;
  float dx = -1.f / 280.f * dsinv;
  checkCuda( cudaMemcpyToSymbol(c_ax, &ax, sizeof(float), 0, cudaMemcpyHostToDevice) );
  checkCuda( cudaMemcpyToSymbol(c_bx, &bx, sizeof(float), 0, cudaMemcpyHostToDevice) );
  checkCuda( cudaMemcpyToSymbol(c_cx, &cx, sizeof(float), 0, cudaMemcpyHostToDevice) );
  checkCuda( cudaMemcpyToSymbol(c_dx, &dx, sizeof(float), 0, cudaMemcpyHostToDevice) );

  dsinv = my-1.f;
  
  float ay =  4.f / 5.f   * dsinv;
  float by = -1.f / 5.f   * dsinv;
  float cy =  4.f / 105.f * dsinv;
  float dy = -1.f / 280.f * dsinv;
  checkCuda( cudaMemcpyToSymbol(c_ay, &ay, sizeof(float), 0, cudaMemcpyHostToDevice) );
  checkCuda( cudaMemcpyToSymbol(c_by, &by, sizeof(float), 0, cudaMemcpyHostToDevice) );
  checkCuda( cudaMemcpyToSymbol(c_cy, &cy, sizeof(float), 0, cudaMemcpyHostToDevice) );
  checkCuda( cudaMemcpyToSymbol(c_dy, &dy, sizeof(float), 0, cudaMemcpyHostToDevice) );

  dsinv = mz-1.f;
  
  float az =  4.f / 5.f   * dsinv;
  float bz = -1.f / 5.f   * dsinv;
  float cz =  4.f / 105.f * dsinv;
  float dz = -1.f / 280.f * dsinv;
  checkCuda( cudaMemcpyToSymbol(c_az, &az, sizeof(float), 0, cudaMemcpyHostToDevice) );
  checkCuda( cudaMemcpyToSymbol(c_bz, &bz, sizeof(float), 0, cudaMemcpyHostToDevice) );
  checkCuda( cudaMemcpyToSymbol(c_cz, &cz, sizeof(float), 0, cudaMemcpyHostToDevice) );
  checkCuda( cudaMemcpyToSymbol(c_dz, &dz, sizeof(float), 0, cudaMemcpyHostToDevice) );

  // Execution configurations for small and large pencil tiles

  grid[0][0]  = dim3(my / sPencils, mz, 1);
  block[0][0] = dim3(mx, sPencils, 1);

  grid[0][1]  = dim3(my / lPencils, mz, 1);
  block[0][1] = dim3(mx, sPencils, 1);

  grid[1][0]  = dim3(mx / sPencils, mz, 1);
  block[1][0] = dim3(sPencils, my, 1);

  grid[1][1]  = dim3(mx / lPencils, mz, 1);
  // we want to use the same number of threads as above,
  // so when we use lPencils instead of sPencils in one
  // dimension, we multiply the other by sPencils/lPencils
  block[1][1] = dim3(lPencils, my * sPencils / lPencils, 1);

  grid[2][0]  = dim3(mx / sPencils, my, 1);
  block[2][0] = dim3(sPencils, mz, 1);

  grid[2][1]  = dim3(mx / lPencils, my, 1);
  block[2][1] = dim3(lPencils, mz * sPencils / lPencils, 1);
}

// A 32x32 output tile uses a sixteen-row thread block. Each thread computes
// two y outputs, while cooperative loads stage the tile and four-row halos.
__global__ void derivative_y(const float *f, float *df, int n, int m,
                             float ay, float by, float cy, float dy)
{
  __shared__ float s_f[40][32];

  const int i = blockIdx.x * 32 + threadIdx.x;
  const int yBase = blockIdx.y * 32;
  const int k = blockIdx.z;

  // Load 32 output rows plus the four neighbors on each side. The endpoint
  // m-1 remains an input row; only indices outside [0,m) are period-(m-1)
  // wrapped, matching the 64-row (period-63) convention.
  for (int tileRow = threadIdx.y; tileRow < 40; tileRow += 16) {
    int sourceY = yBase + tileRow - 4;
    if (sourceY < 0 || sourceY >= m) {
      const int period = (m > 1) ? (m - 1) : 1;
      sourceY %= period;
      if (sourceY < 0)
        sourceY += period;
    }

    if (i < n)
      s_f[tileRow][threadIdx.x] = f[(k * m + sourceY) * n + i];
    else
      s_f[tileRow][threadIdx.x] = 0.0f;
  }

  __syncthreads();

  // threadIdx.x is the contiguous warp dimension. Each thread reuses the
  // shared y tile for two outputs before the block is retired.
  #pragma unroll
  for (int outputRow = threadIdx.y; outputRow < 32; outputRow += 16) {
    const int j = yBase + outputRow;
    if (i < n && j < m) {
      const int sharedRow = outputRow + 4;
      const int globalIdx = (k * m + j) * n + i;

      const float d1 =
          s_f[sharedRow + 1][threadIdx.x] - s_f[sharedRow - 1][threadIdx.x];
      const float d2 =
          s_f[sharedRow + 2][threadIdx.x] - s_f[sharedRow - 2][threadIdx.x];
      const float d3 =
          s_f[sharedRow + 3][threadIdx.x] - s_f[sharedRow - 3][threadIdx.x];
      const float d4 =
          s_f[sharedRow + 4][threadIdx.x] - s_f[sharedRow - 4][threadIdx.x];

      const float pair01 = fmaf(ay, d1, by * d2);
      const float pair23 = fmaf(cy, d3, dy * d4);
      df[globalIdx] = pair01 + pair23;
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

  if (n <= 0 || m <= 0 || k <= 0)
    return;

  const float dsinv = m - 1.f;
  const float ay =  4.f / 5.f   * dsinv;
  const float by = -1.f / 5.f   * dsinv;
  const float cy =  4.f / 105.f * dsinv;
  const float dy = -1.f / 280.f * dsinv;

  const dim3 tileGrid((n + 31) / 32, (m + 31) / 32, k);
  const dim3 tileBlock(32, 16, 1);
  derivative_y<<<tileGrid, tileBlock>>>(A, C, n, m, ay, by, cy, dy);
}
