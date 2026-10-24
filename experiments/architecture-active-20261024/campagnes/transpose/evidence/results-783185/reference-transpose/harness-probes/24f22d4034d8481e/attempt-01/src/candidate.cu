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
#include <stddef.h>
#include <cuda_runtime.h>

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

const int TILE_DIM = 32;
const int NUM_REPS = 100;

// Check errors and print GB/s
void postprocess(const float *ref, const float *res, int n, float ms)
{
  bool passed = true;
  for (int i = 0; i < n; i++)
    if (res[i] != ref[i]) {
      printf("%d %f %f\n", i, res[i], ref[i]);
      printf("%25s\n", "*** FAILED ***");
      passed = false;
      break;
    }
  if (passed)
    printf("%20.2f\n", 2 * n * sizeof(float) * 1e-6 * NUM_REPS / ms );
}

// Each thread owns a 2x2 input subtile; float2 transfers cover its adjacent
// columns. After the shared-memory exchange, each thread emits two float2
// pairs along a contiguous output row.
__global__ void transposeSharedVector2x2(float *odata, const float *idata, int n)
{
  const unsigned int tx = threadIdx.x;
  const unsigned int ty = threadIdx.y;
  const unsigned int tileX = blockIdx.x * TILE_DIM;
  const unsigned int tileY = blockIdx.y * TILE_DIM;
  const unsigned int x = tileX + 2u * tx;
  const unsigned int y = tileY + 2u * ty;
  __shared__ float tile[TILE_DIM][TILE_DIM + 1];

  const size_t inIndex0 = static_cast<size_t>(y) * static_cast<size_t>(n) + x;
  const size_t inIndex1 = static_cast<size_t>(y + 1u) * static_cast<size_t>(n) + x;
  const float2 in0 = *reinterpret_cast<const float2 *>(idata + inIndex0);
  const float2 in1 = *reinterpret_cast<const float2 *>(idata + inIndex1);

  tile[2u * ty][2u * tx] = in0.x;
  tile[2u * ty][2u * tx + 1u] = in0.y;
  tile[2u * ty + 1u][2u * tx] = in1.x;
  tile[2u * ty + 1u][2u * tx + 1u] = in1.y;

  __syncthreads();

  const unsigned int outCol = tileY + 2u * tx;
  for (unsigned int c = 0; c < 2u; ++c) {
    const unsigned int outRow = tileX + 2u * ty + c;
    float2 out;
    out.x = tile[2u * tx][2u * ty + c];
    out.y = tile[2u * tx + 1u][2u * ty + c];
    const size_t outIndex = static_cast<size_t>(outRow) * static_cast<size_t>(n) + outCol;
    *reinterpret_cast<float2 *>(odata + outIndex) = out;
  }
}

extern "C" void run(const float *A, const float *B, float *C, float *scratch,
                    int n, int m, int k, float alpha, float beta)
{
  dim3 grid(n / TILE_DIM, n / TILE_DIM);
  dim3 block(TILE_DIM / 2, TILE_DIM / 2);
  transposeSharedVector2x2<<<grid, block>>>(C, A, n);
}
