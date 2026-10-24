#include <cuda_runtime.h>
#include <cub/block/block_reduce.cuh>

__global__ void sum_abs(const float* x, float* y, int n)
{
    using BlockReduce = cub::BlockReduce<float, 256>;
    __shared__ typename BlockReduce::TempStorage temp;

    float partial = 0.0f;
    for (size_t i = size_t(blockIdx.x) * blockDim.x + threadIdx.x;
         i < size_t(n);
         i += size_t(blockDim.x) * gridDim.x) {
        partial += fabsf(x[i]);
    }

    const float total = BlockReduce(temp).Sum(partial);
    if (threadIdx.x == 0) {
        atomicAdd(y, total);
    }
}

extern "C" void run(const void* x, const void* k, const void* gy, void* out,
                    void* scratch, int n, int h, int l, int ks)
{
    cudaMemsetAsync(out, 0, sizeof(float));

    if (n <= 0) {
        return;
    }

    int blocks = n / 256 + (n % 256 != 0);
    if (blocks > 1024) {
        blocks = 1024;
    }
    sum_abs<<<blocks, 256>>>((const float*)x, (float*)out, n);
}
