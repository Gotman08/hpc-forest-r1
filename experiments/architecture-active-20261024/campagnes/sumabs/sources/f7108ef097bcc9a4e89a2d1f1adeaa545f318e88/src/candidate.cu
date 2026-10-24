#include <cuda_runtime.h>
#include <cub/block/block_reduce.cuh>

__global__ void sum_abs_atomic(const float* x, float* y, int n)
{
    using BlockReduce = cub::BlockReduce<float, 256>;
    __shared__ typename BlockReduce::TempStorage temp_storage;

    const size_t stride = static_cast<size_t>(blockDim.x) * gridDim.x;
    const size_t four_stride = stride * 4;
    size_t i = static_cast<size_t>(blockIdx.x) * blockDim.x + threadIdx.x;

    float sum0 = 0.0f;
    float sum1 = 0.0f;
    float sum2 = 0.0f;
    float sum3 = 0.0f;

    for (; i < static_cast<size_t>(n); i += four_stride) {
        sum0 += fabsf(x[i]);
        const size_t i1 = i + stride;
        const size_t i2 = i + stride * 2;
        const size_t i3 = i + stride * 3;
        if (i1 < static_cast<size_t>(n)) sum1 += fabsf(x[i1]);
        if (i2 < static_cast<size_t>(n)) sum2 += fabsf(x[i2]);
        if (i3 < static_cast<size_t>(n)) sum3 += fabsf(x[i3]);
    }

    const float thread_sum = (sum0 + sum1) + (sum2 + sum3);
    const float block_sum = BlockReduce(temp_storage).Sum(thread_sum);
    if (threadIdx.x == 0) atomicAdd(y, block_sum);
}

extern "C" void run(const void* x, const void* k, const void* gy, void* out,
                    void* scratch, int n, int h, int l, int ks)
{
    cudaMemsetAsync(out, 0, sizeof(float));
    if (n <= 0) return;

    int blocks = (n - 1) / 256 + 1;
    if (blocks > 512) blocks = 512;
    sum_abs_atomic<<<blocks, 256>>>(static_cast<const float*>(x),
                                   static_cast<float*>(out), n);
}
