#include <cuda_runtime.h>
/* Copyright (c) 1993-2015, NVIDIA CORPORATION. All rights reserved.
 *
 * Redistribution and use in source and binary forms, with or without
 * modification, are permitted provided that the following conditions
 * are met:
 *  * Redistributions of source code must retain the above copyright
 *    notice, this list of conditions and the following disclaimer.
 *  * Redistributions in binary form must reproduce the above copyright
 *    notice, this list of conditions and the following disclaimer
 *    in the documentation and/or other materials provided with the
 *    distribution.
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

// Stencil coefficients.
__constant__ float c_ax, c_bx, c_cx, c_dx;
__constant__ float c_ay, c_by, c_cy, c_dy;
__constant__ float c_az, c_bz, c_cz, c_dz;

// Host routine to set constant data.
void setDerivativeParameters()
{
  // Stencil weights (for unit length problem).
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
}

// Apply the specified single-step Y boundary correction, preserving 63.
__device__ __forceinline__ int correctedY(int q)
{
  if (q < 0) {
    q += 63;
  } else if (q > 63) {
    q -= 63;
  }
  return q;
}

// One direct-global-load output per thread. Each warp spans adjacent X values.
__global__ void derivative_y_direct(const float *f, float *df)
{
  const int i = blockIdx.x * blockDim.x + threadIdx.x;
  const int j = blockIdx.y * blockDim.y + threadIdx.y;
  const int k = blockIdx.z;
  const int row = k * mx * my + i;
  const int output = row + j * mx;

  const int jm1 = correctedY(j - 1);
  const int jp1 = correctedY(j + 1);
  const int jm2 = correctedY(j - 2);
  const int jp2 = correctedY(j + 2);
  const int jm3 = correctedY(j - 3);
  const int jp3 = correctedY(j + 3);
  const int jm4 = correctedY(j - 4);
  const int jp4 = correctedY(j + 4);

  const float fm1 = f[row + jm1 * mx];
  const float fp1 = f[row + jp1 * mx];
  const float fm2 = f[row + jm2 * mx];
  const float fp2 = f[row + jp2 * mx];
  const float fm3 = f[row + jm3 * mx];
  const float fp3 = f[row + jp3 * mx];
  const float fm4 = f[row + jm4 * mx];
  const float fp4 = f[row + jp4 * mx];

  df[output] =
    ( c_ay * (fp1 - fm1)
    + c_by * (fp2 - fm2)
    + c_cy * (fp3 - fm3)
    + c_dy * (fp4 - fm4) );
}

extern "C" void run(const float *A, const float *B, float *C, float *scratch,
                    int n, int m, int k, float alpha, float beta)
{
  static bool initialized = false;
  if (!initialized) {
    setDerivativeParameters();
    initialized = true;
  }

  (void)B;
  (void)scratch;
  (void)n;
  (void)m;
  (void)k;
  (void)alpha;
  (void)beta;

  // 16 warps per CTA; each warp maps to one adjacent-X output row.
  const dim3 block(32, 16, 1);
  const dim3 grid(mx / 32, my / 16, mz);
  derivative_y_direct<<<grid, block>>>(A, C);
}
