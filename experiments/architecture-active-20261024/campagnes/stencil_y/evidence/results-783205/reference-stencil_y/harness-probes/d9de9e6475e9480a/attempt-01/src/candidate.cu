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
  if ((mx % sPencils != 0) || (my %sPencils != 0) || (mz % sPencils != 0)) {
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

// Match the baseline shared-tile halo convention: negative rows wrap by
// my-1, while rows above the final stored row wrap back by my-1.
__device__ __forceinline__ int baseline_y_index(int y)
{
  if (y < 0) return y + (my - 1);
  if (y >= my) return y - (my - 1);
  return y;
}

__device__ __forceinline__ float load_y_value(const float *f, int k, int y, int i)
{
  const int wrappedY = baseline_y_index(y);
  return f[k * mx * my + wrappedY * mx + i];
}

__device__ __forceinline__ float calc_derivative_y(
    float m4, float m3, float m2, float m1,
    float p1, float p2, float p3, float p4)
{
  return ( c_ay * (p1 - m1)
         + c_by * (p2 - m2)
         + c_cy * (p3 - m3)
         + c_dy * (p4 - m4) );
}

// Each warp spans contiguous x positions. A thread computes four consecutive
// y outputs, loading their 12-row union once into registers instead of using
// the shared-memory tile and barriers.
__global__ void derivative_y(const float *f, float *df)
{
  const int i = blockIdx.x * blockDim.x + threadIdx.x;
  if (i >= mx) return;

  const int k = blockIdx.z;
  const int y0 = blockIdx.y * (blockDim.y * 4) + threadIdx.y * 4;
  const int base = k * mx * my + i;

  const float r0  = load_y_value(f, k, y0 - 4, i);
  const float r1  = load_y_value(f, k, y0 - 3, i);
  const float r2  = load_y_value(f, k, y0 - 2, i);
  const float r3  = load_y_value(f, k, y0 - 1, i);
  const float r4  = load_y_value(f, k, y0,     i);
  const float r5  = load_y_value(f, k, y0 + 1, i);
  const float r6  = load_y_value(f, k, y0 + 2, i);
  const float r7  = load_y_value(f, k, y0 + 3, i);
  const float r8  = load_y_value(f, k, y0 + 4, i);
  const float r9  = load_y_value(f, k, y0 + 5, i);
  const float r10 = load_y_value(f, k, y0 + 6, i);
  const float r11 = load_y_value(f, k, y0 + 7, i);

  if (y0 < my)
    df[base + y0 * mx] = calc_derivative_y(r0, r1, r2, r3, r5, r6, r7, r8);
  if (y0 + 1 < my)
    df[base + (y0 + 1) * mx] = calc_derivative_y(r1, r2, r3, r4, r6, r7, r8, r9);
  if (y0 + 2 < my)
    df[base + (y0 + 2) * mx] = calc_derivative_y(r2, r3, r4, r5, r7, r8, r9, r10);
  if (y0 + 3 < my)
    df[base + (y0 + 3) * mx] = calc_derivative_y(r3, r4, r5, r6, r8, r9, r10, r11);
}

// y derivative using contiguous x lanes and four register-blocked y outputs
extern "C" void run(const float*A,const float*B,float*C,float*scratch,int n,int m,int k,float alpha,float beta)
{ static bool initialized=false; if(!initialized){setDerivativeParameters();initialized=true;} dim3 rbBlock(32,2,1); dim3 rbGrid((mx + rbBlock.x - 1) / rbBlock.x, (my + 7) / 8, mz); derivative_y<<<rbGrid,rbBlock>>>(A,C); }
