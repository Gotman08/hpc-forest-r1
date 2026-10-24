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
 * OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING
 * NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
 * SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
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

// Exchange one lane-index bit with the matching register-index bit.
// Every shuffle is confined to the caller's 32-lane warp.
template <int BIT>
__device__ __forceinline__
void exchangeLaneRegisterBit(unsigned int (&values)[32], int lane)
{
  #pragma unroll
  for (int base = 0; base < 32; base += 2 * BIT) {
    #pragma unroll
    for (int offset = 0; offset < BIT; ++offset) {
      const int low = base + offset;
      const int high = low + BIT;
      // The receiving slot is the opposite bit from the sender's lane bit.
      const unsigned int outgoing = (lane & BIT) ? values[low] : values[high];
      const unsigned int incoming = __shfl_xor_sync(0xffffffffu, outgoing, BIT, 32);
      if ((lane & BIT) == 0)
        values[high] = incoming;
      else
        values[low] = incoming;
    }
  }
}

// One warp owns a complete 32x32 tile. Initially lane c owns all rows for
// input column c. Five lane/register-bit exchanges leave lane r owning the
// tile values for input row r, ready for contiguous output-column stores.
__global__ void transposeWarpRegister(float *odata, const float *idata, int n)
{
  const size_t width = static_cast<size_t>(n);
  const size_t tileCount = width / TILE_DIM;
  const size_t tileX = static_cast<size_t>(blockIdx.x) * blockDim.y + threadIdx.y;
  if (tileX >= tileCount)
    return;

  const int lane = threadIdx.x;
  for (size_t tileY = static_cast<size_t>(blockIdx.y);
       tileY < tileCount;
       tileY += static_cast<size_t>(gridDim.y)) {
    unsigned int values[32];
    const size_t inputBase = tileY * TILE_DIM * width + tileX * TILE_DIM;

    // For each row, the warp reads 32 adjacent input columns.
    #pragma unroll
    for (int row = 0; row < 32; ++row)
      values[row] = __float_as_uint(idata[inputBase + static_cast<size_t>(row) * width + static_cast<size_t>(lane)]);

    exchangeLaneRegisterBit<1>(values, lane);
    exchangeLaneRegisterBit<2>(values, lane);
    exchangeLaneRegisterBit<4>(values, lane);
    exchangeLaneRegisterBit<8>(values, lane);
    exchangeLaneRegisterBit<16>(values, lane);

    // After the exchanges, each lane is an input row and each register slot
    // is an input column. Thus lanes store adjacent output columns.
    const size_t outputColumn = tileY * TILE_DIM + static_cast<size_t>(lane);
    #pragma unroll
    for (int column = 0; column < 32; ++column) {
      const size_t outputRow = tileX * TILE_DIM + static_cast<size_t>(column);
      odata[outputRow * width + outputColumn] = __uint_as_float(values[column]);
    }
  }
}

extern "C" void run(const float *A, const float *B, float *C, float *scratch,
                    int n, int m, int k, float alpha, float beta)
{
  (void)B;
  (void)scratch;
  (void)m;
  (void)k;
  (void)alpha;
  (void)beta;

  const unsigned int tiles = static_cast<unsigned int>(n / TILE_DIM);
  const unsigned int blocksX = (tiles + 3u) / 4u;
  // Keep the y grid within CUDA's portable 2-D grid limit; the kernel strides
  // over additional tile rows when needed.
  const unsigned int blocksY = tiles < 65535u ? tiles : 65535u;
  transposeWarpRegister<<<dim3(blocksX, blocksY), dim3(TILE_DIM, 4, 1)>>>(C, A, n);
}
