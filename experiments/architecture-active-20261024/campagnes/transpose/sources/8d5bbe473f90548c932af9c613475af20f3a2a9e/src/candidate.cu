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

// Each warp handles a 4-row by 32-column input strip. Four-lane subgroups
// exchange the low two lane bits with the two register-index bits, entirely
// within their own warp, to transpose 4x4 subtiles.
__global__ void transposeWarpRegister4(float *odata, const float *idata, int width)
{
  const int lane = threadIdx.x;
  const int tileX = blockIdx.x * TILE_DIM;
  const int inputX = tileX + lane;
  const int inputY = blockIdx.y * TILE_DIM + threadIdx.y * 4;
  unsigned int values[4];

  // Adjacent lanes load adjacent input columns for each of four rows.
  #pragma unroll
  for (int row = 0; row < 4; ++row) {
    const size_t index = (size_t)(inputY + row) * (size_t)width + (size_t)inputX;
    values[row] = __float_as_uint(idata[index]);
  }

  // Swap each of two lane bits with its matching register-index bit.
  // Width four confines each exchange to a same-warp four-lane subgroup.
  const unsigned int fullWarpMask = 0xffffffffu;
  #pragma unroll
  for (int stage = 0; stage < 2; ++stage) {
    const int bit = 1 << stage;
    #pragma unroll
    for (int low = 0; low < 4; ++low) {
      if ((low & bit) == 0) {
        const int high = low + bit;
        const unsigned int outgoing = (lane & bit) ? values[low] : values[high];
        const unsigned int incoming = __shfl_xor_sync(fullWarpMask, outgoing, bit, 4);
        if (lane & bit)
          values[low] = incoming;
        else
          values[high] = incoming;
      }
    }
  }

  // After exchange, lane low bits select the input row (output column),
  // while the register index supplies the input column's low bits. Each
  // four-lane subgroup therefore writes four contiguous output columns.
  const int outputY = tileX + (lane & ~3);
  const int outputX = inputY + (lane & 3);
  #pragma unroll
  for (int column = 0; column < 4; ++column) {
    const size_t index = (size_t)(outputY + column) * (size_t)width + (size_t)outputX;
    odata[index] = __uint_as_float(values[column]);
  }
}

extern "C" void run(const float *A, const float *B, float *C, float *scratch,
                    int n, int m, int k, float alpha, float beta)
{
  dim3 grid(n / TILE_DIM, n / TILE_DIM);
  dim3 block(TILE_DIM, 8);
  transposeWarpRegister4<<<grid, block>>>(C, A, n);
}
