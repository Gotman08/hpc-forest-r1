#include <cuda_runtime.h>
/* Copyright (c) 1993-2015, NVIDIA CORPORATION. All rights reserved.
 *
 * Redistribution and use in source and binary forms, with or without
 * modification, are permitted provided that the following conditions
 * are met:
 *  * Redistributions of source code must retain the above copyright
 *    notice, this list of conditions and the following disclaimer.
 *  * Redistributions in binary form must reproduce the above copyright
 *    notice, this list of conditions and the following disclaimer in
 *    the documentation and/or other materials provided with the distribution.
 *  * Neither the name of NVIDIA CORPORATION nor the names of its
 *    contributors may be used to endorse or promote products derived
 *    from this software without specific prior written permission.
 *
 * THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS ``AS IS'' AND ANY
 * EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
 * WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
 * DISCLAIMED.  IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE
 * LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
 * CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
 * SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
 * INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
 * CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
 * ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
 * POSSIBILITY OF SUCH DAMAGE.
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

// Shared-memory pencil configurations retained for the parameter setup.
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

  // Existing configurations for the small and large pencil variants.
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

__device__ __forceinline__ int wrap_y_index(int y)
{
  const int period = my - 1;
  const int wrapped = y % period;
  return wrapped < 0 ? wrapped + period : wrapped;
}

// Each thread computes two adjacent y outputs from their shared 10-row
// neighborhood. Warp lanes cover contiguous x coordinates; the y halo repeats
// with period my - 1.
__global__ void derivative_y(const float *f, float *df)
{
  const int i = blockIdx.x * blockDim.x + threadIdx.x;
  const int y0 = blockIdx.y * (blockDim.y * 2) + threadIdx.y * 2;
  const int k = blockIdx.z;

  if (i >= mx || y0 >= my || k >= mz) return;

  const float v0 = f[(k * my + wrap_y_index(y0 - 4)) * mx + i];
  const float v1 = f[(k * my + wrap_y_index(y0 - 3)) * mx + i];
  const float v2 = f[(k * my + wrap_y_index(y0 - 2)) * mx + i];
  const float v3 = f[(k * my + wrap_y_index(y0 - 1)) * mx + i];
  const float v4 = f[(k * my + wrap_y_index(y0    )) * mx + i];
  const float v5 = f[(k * my + wrap_y_index(y0 + 1)) * mx + i];
  const float v6 = f[(k * my + wrap_y_index(y0 + 2)) * mx + i];
  const float v7 = f[(k * my + wrap_y_index(y0 + 3)) * mx + i];
  const float v8 = f[(k * my + wrap_y_index(y0 + 4)) * mx + i];
  const float v9 = f[(k * my + wrap_y_index(y0 + 5)) * mx + i];

  df[(k * my + y0) * mx + i] =
    ( c_ay * (v5 - v3)
    + c_by * (v6 - v2)
    + c_cy * (v7 - v1)
    + c_dy * (v8 - v0) );

  if (y0 + 1 < my) {
    df[(k * my + y0 + 1) * mx + i] =
      ( c_ay * (v6 - v4)
      + c_by * (v7 - v3)
      + c_cy * (v8 - v2)
      + c_dy * (v9 - v1) );
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

  const dim3 blockY(32, 2, 1);
  const dim3 gridY((mx + blockY.x - 1) / blockY.x,
                   (my + 2 * blockY.y - 1) / (2 * blockY.y),
                   mz);
  derivative_y<<<gridY, blockY>>>(A, C);
}
