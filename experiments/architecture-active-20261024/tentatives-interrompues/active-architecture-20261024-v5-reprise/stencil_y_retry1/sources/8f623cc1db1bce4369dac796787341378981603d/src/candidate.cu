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
 * THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AS IS AND ANY
 * EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
 * IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR
 * PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR
 * CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL,
 * EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO,
 * PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR
 * PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY
 * OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
 * (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
 * OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
 */

__device__ __forceinline__ int wrap_y_neighbor(int j, int delta, int period)
{
  int q = j + delta;
  if (period <= 0) return 0;

  // For the 64-point Y dimension this is exactly the prescribed single
  // correction by 63, while retaining the in-range endpoint at index 63.
  if (period >= 4) {
    if (q < 0) q += period;
    else if (q > period) q -= period;
  } else {
    // Also handle smaller valid dimensions where an offset can cross more
    // than one period.
    while (q < 0) q += period;
    while (q > period) q -= period;
  }
  return q;
}

__global__ void derivative_y_direct(const float *f, float *df,
                                   int nx, int ny, int nz,
                                   float ay, float by, float cy, float dy)
{
  const int i = blockIdx.x * blockDim.x + threadIdx.x;
  const int j = blockIdx.y * blockDim.y + threadIdx.y;
  const int k = blockIdx.z * blockDim.z + threadIdx.z;
  if (i >= nx || j >= ny || k >= nz) return;

  const int period = ny - 1;
  const int jm1 = wrap_y_neighbor(j, -1, period);
  const int jp1 = wrap_y_neighbor(j,  1, period);
  const int jm2 = wrap_y_neighbor(j, -2, period);
  const int jp2 = wrap_y_neighbor(j,  2, period);
  const int jm3 = wrap_y_neighbor(j, -3, period);
  const int jp3 = wrap_y_neighbor(j,  3, period);
  const int jm4 = wrap_y_neighbor(j, -4, period);
  const int jp4 = wrap_y_neighbor(j,  4, period);

  const size_t plane = (size_t)nx * (size_t)ny;
  const size_t line = (size_t)k * plane + (size_t)i;
  const size_t index = line + (size_t)j * (size_t)nx;

  const float fm1 = f[line + (size_t)jm1 * (size_t)nx];
  const float fp1 = f[line + (size_t)jp1 * (size_t)nx];
  const float fm2 = f[line + (size_t)jm2 * (size_t)nx];
  const float fp2 = f[line + (size_t)jp2 * (size_t)nx];
  const float fm3 = f[line + (size_t)jm3 * (size_t)nx];
  const float fp3 = f[line + (size_t)jp3 * (size_t)nx];
  const float fm4 = f[line + (size_t)jm4 * (size_t)nx];
  const float fp4 = f[line + (size_t)jp4 * (size_t)nx];

  df[index] =
      ay * (fp1 - fm1)
    + by * (fp2 - fm2)
    + cy * (fp3 - fm3)
    + dy * (fp4 - fm4);
}

extern "C" void run(const float *A, const float *B, float *C,
                    float *scratch, int n, int m, int k,
                    float alpha, float beta)
{
  (void)B;
  (void)scratch;
  (void)alpha;
  (void)beta;
  if (n <= 0 || m <= 0 || k <= 0) return;

  const float dsinv = (float)m - 1.0f;
  const float ay =  4.0f / 5.0f   * dsinv;
  const float by = -1.0f / 5.0f   * dsinv;
  const float cy =  4.0f / 105.0f * dsinv;
  const float dy = -1.0f / 280.0f * dsinv;

  // Each warp covers 32 adjacent X outputs at one fixed Y and Z.
  // The 2-by-8 Y/Z grouping keeps 512 threads per block while contrasting
  // with the measured 8-by-2 grouping.
  const dim3 block(32, 2, 8);
  const dim3 grid((n + block.x - 1) / block.x,
                  (m + block.y - 1) / block.y,
                  (k + block.z - 1) / block.z);
  derivative_y_direct<<<grid, block>>>(A, C, n, m, k, ay, by, cy, dy);
}
