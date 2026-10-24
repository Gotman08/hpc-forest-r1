#include <cuda_runtime.h>
#include <stddef.h>

// Apply the exact boundary correction; index 63 remains in range.
__device__ __forceinline__ int wrap_y(int q)
{
  if (q < 0)
    q += 63;
  else if (q > 63)
    q -= 63;
  return q;
}

// Each warp computes adjacent X outputs at one fixed Y and Z.
__global__ void derivative_y_direct(const float *A, float *C,
                                    int n, int m, int k,
                                    float ay, float by, float cy, float dy)
{
  const int i = blockIdx.x * blockDim.x + threadIdx.x;
  const int j = blockIdx.y * blockDim.y + threadIdx.y;
  const int z = blockIdx.z * blockDim.z + threadIdx.z;
  if (i >= n || j >= m || z >= k)
    return;

  const size_t row_base = (static_cast<size_t>(z) * static_cast<size_t>(m))
                        * static_cast<size_t>(n) + static_cast<size_t>(i);
  const size_t y_stride = static_cast<size_t>(n);

  const int jm1 = wrap_y(j - 1);
  const int jp1 = wrap_y(j + 1);
  const int jm2 = wrap_y(j - 2);
  const int jp2 = wrap_y(j + 2);
  const int jm3 = wrap_y(j - 3);
  const int jp3 = wrap_y(j + 3);
  const int jm4 = wrap_y(j - 4);
  const int jp4 = wrap_y(j + 4);

  const float fm1 = A[row_base + static_cast<size_t>(jm1) * y_stride];
  const float fp1 = A[row_base + static_cast<size_t>(jp1) * y_stride];
  const float fm2 = A[row_base + static_cast<size_t>(jm2) * y_stride];
  const float fp2 = A[row_base + static_cast<size_t>(jp2) * y_stride];
  const float fm3 = A[row_base + static_cast<size_t>(jm3) * y_stride];
  const float fp3 = A[row_base + static_cast<size_t>(jp3) * y_stride];
  const float fm4 = A[row_base + static_cast<size_t>(jm4) * y_stride];
  const float fp4 = A[row_base + static_cast<size_t>(jp4) * y_stride];

  C[row_base + static_cast<size_t>(j) * y_stride] =
      ay * (fp1 - fm1)
    + by * (fp2 - fm2)
    + cy * (fp3 - fm3)
    + dy * (fp4 - fm4);
}

extern "C" void run(const float *A, const float *B, float *C,
                    float *scratch, int n, int m, int k,
                    float alpha, float beta)
{
  if (n <= 0 || m <= 0 || k <= 0)
    return;

  const float scale = static_cast<float>(m) - 1.0f;
  const float ay = (4.0f / 5.0f) * scale;
  const float by = (-1.0f / 5.0f) * scale;
  const float cy = (4.0f / 105.0f) * scale;
  const float dy = (-1.0f / 280.0f) * scale;

  // Same 512 threads per CTA as (32,8,2), but with less Y and more Z grouping.
  const dim3 block(32, 4, 4);
  const dim3 grid(n / 32 + (n % 32 != 0),
                  m / 4 + (m % 4 != 0),
                  k / 4 + (k % 4 != 0));
  derivative_y_direct<<<grid, block>>>(A, C, n, m, k, ay, by, cy, dy);
}
