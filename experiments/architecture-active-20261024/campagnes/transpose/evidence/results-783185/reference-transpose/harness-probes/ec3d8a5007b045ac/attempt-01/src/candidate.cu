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
const int TILE_ROWS = 64;
const int BLOCK_ROWS = 8;
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

// Rectangular transpose with an XOR-swizzled shared-memory layout.
// Loads and stores remain coalesced; the swizzle replaces the padded stride.
__global__ void transposeShared64x32Xor(float *odata, const float *idata, int n)
{
  __shared__ float tile[TILE_ROWS][TILE_DIM];

  const int tileCol = blockIdx.x * TILE_DIM;
  const int tileRow = blockIdx.y * TILE_ROWS;
  const int x = tileCol + threadIdx.x;

  for (int j = 0; j < TILE_ROWS; j += BLOCK_ROWS) {
    const int rowLocal = threadIdx.y + j;
    const int row = tileRow + rowLocal;
    if (row < n && x < n)
      tile[rowLocal][threadIdx.x ^ (rowLocal & (TILE_DIM - 1))] =
          idata[(size_t)row * (size_t)n + (size_t)x];
  }

  __syncthreads();

  for (int i = 0; i < TILE_ROWS; i += TILE_DIM) {
    for (int j = 0; j < TILE_DIM; j += BLOCK_ROWS) {
      const int inputRowLocal = i + threadIdx.x;
      const int inputColLocal = threadIdx.y + j;
      const int outRow = tileCol + inputColLocal;
      const int outCol = tileRow + inputRowLocal;
      if (outRow < n && outCol < n)
        odata[(size_t)outRow * (size_t)n + (size_t)outCol] =
            tile[inputRowLocal][inputColLocal ^
                                (inputRowLocal & (TILE_DIM - 1))];
    }
  }
}

extern "C" void run(const float *A, const float *B, float *C, float *scratch,
                    int n, int m, int k, float alpha, float beta)
{
  const int gridRows = n / TILE_ROWS + ((n % TILE_ROWS) != 0);
  transposeShared64x32Xor<<<dim3(n / TILE_DIM, gridRows),
                            dim3(TILE_DIM, BLOCK_ROWS)>>>(C, A, n);
}
