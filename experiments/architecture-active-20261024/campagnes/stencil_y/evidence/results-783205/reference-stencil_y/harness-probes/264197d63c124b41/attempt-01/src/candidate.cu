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
 * EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
 * WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
 * DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE
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

// Reference pencil sizes used by the other launch presets.
const int sPencils = 8;
const int lPencils = 32;

// Active y-derivative tile: 32 x pencils by 16 output rows.
const int yTilePencils = 32;
const int yTileRows = 16;

dim3 grid[3][2], block[3][2];

// stencil coefficients
__constant__ float c_ax, c_bx, c_cx, c_dx;
__constant__ float c_ay, c_by, c_cy, c_dy;
__constant__ float c_az, c_bz, c_cz, c_dz;

// host routine to set constant data
void setDerivativeParameters()
{
  // check to make sure dimensions are integral multiples of sPencils
  if ((mx % sPencils != 0) || (my % sPencils != 0) || (mz % sPencils != 0)) {
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

  grid[1][0]  = dim3(mx / yTilePencils, my / yTileRows, mz);
  block[1][0] = dim3(yTilePencils, yTileRows, 1);

  grid[1][1]  = dim3(mx / lPencils, mz, 1);
  // Keep the same number of threads when using lPencils in one dimension.
  block[1][1] = dim3(lPencils, my * sPencils / lPencils, 1);

  grid[2][0]  = dim3(mx / sPencils, my, 1);
  block[2][0] = dim3(sPencils, mz, 1);

  grid[2][1]  = dim3(mx / lPencils, my, 1);
  block[2][1] = dim3(lPencils, mz * sPencils / lPencils, 1);
}

// y derivative using a 32-by-16 output tile with radius-4 shared halos.
__global__ void derivative_y(float *f, float *df)
{
  __shared__ float s_f[yTileRows + 8][yTilePencils];

  int i = blockIdx.x * blockDim.x + threadIdx.x;
  int j = blockIdx.y * yTileRows + threadIdx.y;
  int k = blockIdx.z;
  int sj = threadIdx.y + 4;
  int globalIdx = k * mx * my + j * mx + i;

  s_f[sj][threadIdx.x] = f[globalIdx];

  if (threadIdx.y < 4) {
    int lowerY = blockIdx.y * yTileRows + threadIdx.y - 4;
    int upperY = blockIdx.y * yTileRows + yTileRows + threadIdx.y;

    // Match the baseline period-63 endpoint mapping for both y halos.
    if (lowerY < 0) lowerY += my - 1;
    if (lowerY >= my) lowerY -= my - 1;
    if (upperY < 0) upperY += my - 1;
    if (upperY >= my) upperY -= my - 1;

    int lowerIdx = k * mx * my + lowerY * mx + i;
    int upperIdx = k * mx * my + upperY * mx + i;
    s_f[threadIdx.y][threadIdx.x] = f[lowerIdx];
    s_f[yTileRows + 4 + threadIdx.y][threadIdx.x] = f[upperIdx];
  }

  __syncthreads();

  df[globalIdx] =
    ( c_ay * ( s_f[sj+1][threadIdx.x] - s_f[sj-1][threadIdx.x] )
    + c_by * ( s_f[sj+2][threadIdx.x] - s_f[sj-2][threadIdx.x] )
    + c_cy * ( s_f[sj+3][threadIdx.x] - s_f[sj-3][threadIdx.x] )
    + c_dy * ( s_f[sj+4][threadIdx.x] - s_f[sj-4][threadIdx.x] ) );
}

#include <cuda_runtime.h>
extern "C" void run(const float*A,const float*B,float*C,float*scratch,int n,int m,int k,float alpha,float beta)
{
  static bool initialized = false;
  if (!initialized) {
    setDerivativeParameters();
    initialized = true;
  }
  derivative_y<<<grid[1][0], block[1][0]>>>((float*)A, C);
}
