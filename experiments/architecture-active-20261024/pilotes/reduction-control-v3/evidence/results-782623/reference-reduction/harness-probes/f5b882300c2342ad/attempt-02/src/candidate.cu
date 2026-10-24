#include <cuda_runtime.h>
#include <stddef.h>

/* Convert a 32-bit modular sum to int without an out-of-range cast. */
__device__ __forceinline__ int uintBitsToInt(unsigned int value)
{
    if (value <= 0x7fffffffu) {
        return static_cast<int>(value);
    }
    return -1 - static_cast<int>(~value);
}

/* Use the native warp integer reduction where available, with a fallback. */
__device__ __forceinline__ unsigned int warpReduceSum(unsigned int value)
{
#if defined(__CUDA_ARCH__) && (__CUDA_ARCH__ >= 800)
    return __reduce_add_sync(0xffffffffu, value);
#else
    for (int offset = warpSize / 2; offset > 0; offset >>= 1) {
        value += __shfl_down_sync(0xffffffffu, value, offset);
    }
    return value;
#endif
}

__global__ void reduceWarpFirst(const int *g_idata, int *g_odata,
                               unsigned int n)
{
    __shared__ unsigned int warp_sums[4];

    const unsigned int tid = threadIdx.x;
    const unsigned int i = blockIdx.x * blockDim.x + tid;
    const unsigned int value =
        (i < n) ? static_cast<unsigned int>(g_idata[i]) : 0u;

    const unsigned int warp_sum = warpReduceSum(value);
    if ((tid & 31u) == 0u) {
        warp_sums[tid >> 5] = warp_sum;
    }
    __syncthreads();

    if (tid < 32u) {
        unsigned int block_sum = (tid < 4u) ? warp_sums[tid] : 0u;
        block_sum = warpReduceSum(block_sum);
        if (tid == 0u) {
            g_odata[blockIdx.x] = uintBitsToInt(block_sum);
        }
    }
}

extern "C" void run(const void *x, const void *k, const void *gy,
                    void *out, void *scratch, int n, int h, int l, int ks)
{
    if (n <= 0) {
        cudaMemsetAsync(out, 0, sizeof(int));
        return;
    }

    unsigned int count = static_cast<unsigned int>(n);
    const int *input = static_cast<const int *>(x);
    int *scratch_base = static_cast<int *>(scratch);
    bool flip = false;

    while (count > 1u) {
        const unsigned int blocks = count / 128u + (count % 128u != 0u);
        int *dest = flip
            ? scratch_base + static_cast<size_t>(n) + 32768u
            : scratch_base;

        reduceWarpFirst<<<blocks, 128>>>(input, dest, count);
        input = dest;
        count = blocks;
        flip = !flip;
    }

    cudaMemcpyAsync(out, input, sizeof(int), cudaMemcpyDeviceToDevice);
}
