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
 *    contributors may be used to endorse or promote products derived from
 *    this software without specific prior written permission.
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

#include <cuda_runtime.h>
#include <stddef.h>

constexpr int TILE_DIM = 32;
constexpr int VECTOR_WIDTH = 4;

// Vectorized global transfers combined with an XOR-swizzled shared tile.
// The XOR mapping permutes columns within each row and is its own inverse.
__global__ void transposeVectorizedXor(float *odata, const float *idata,
                                       int width)
{
  __shared__ unsigned int tile[TILE_DIM][TILE_DIM];

  const int segment = threadIdx.x;
  const int row = threadIdx.y;
  const int col = segment * VECTOR_WIDTH;
  const int inputRow = blockIdx.y * TILE_DIM + row;
  const int inputCol = blockIdx.x * TILE_DIM + col;
  const size_t inputIndex = static_cast<size_t>(inputRow) *
                            static_cast<size_t>(width) +
                            static_cast<size_t>(inputCol);

  const uint4 values = reinterpret_cast<const uint4 *>(idata + inputIndex)[0];
  tile[row][(col + 0) ^ row] = values.x;
  tile[row][(col + 1) ^ row] = values.y;
  tile[row][(col + 2) ^ row] = values.z;
  tile[row][(col + 3) ^ row] = values.w;

  __syncthreads();

  const int outputRow = blockIdx.x * TILE_DIM + row;
  const int outputCol = blockIdx.y * TILE_DIM + col;
  const size_t outputIndex = static_cast<size_t>(outputRow) *
                             static_cast<size_t>(width) +
                             static_cast<size_t>(outputCol);

  uint4 transposed;
  transposed.x = tile[col + 0][row ^ (col + 0)];
  transposed.y = tile[col + 1][row ^ (col + 1)];
  transposed.z = tile[col + 2][row ^ (col + 2)];
  transposed.w = tile[col + 3][row ^ (col + 3)];
  reinterpret_cast<uint4 *>(odata + outputIndex)[0] = transposed;
}

extern "C" void run(const float *A, const float *B, float *C, float *scratch,
                    int n, int m, int k, float alpha, float beta)
{
  transposeVectorizedXor<<<dim3(n / TILE_DIM, n / TILE_DIM),
                           dim3(TILE_DIM / VECTOR_WIDTH, TILE_DIM)>>>(C, A, n);
}
