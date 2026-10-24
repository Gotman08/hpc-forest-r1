#include <cuda_runtime.h>
#include <cub/block/block_reduce.cuh>

__global__ void sum_abs(const float* x, float* y, int n)
{
    using BlockReduce = cub::BlockReduce<float, 256>;
    __shared__ typename BlockReduce::TempStorage temp;

    const size_t length = static_cast<size_t>(n);
    const size_t stride = static_cast<size_t>(blockDim.x) * gridDim.x;
    const size_t first = static_cast<size_t>(blockIdx.x) * blockDim.x + threadIdx.x;

    float sum0 = 0.0f;
    float sum1 = 0.0f;
    float sum2 = 0.0f;
    float sum3 = 0.0f;

    for (size_t i = first; i < length; i += 4 * stride) {
        if (i < length) {
            sum0 += fabsf(x[i]);
        }
        if (i + stride < length) {
            sum1 += fabsf(x[i + stride]);
        }
        if (i + 2 * stride < length) {
            sum2 += fabsf(x[i + 2 * stride]);
        }
        if (i + 3 * stride < length) {
            sum3 += fabsf(x[i + 3 * stride]);
        }
    }

    const float total = BlockReduce(temp).Sum(sum0 + sum1 + sum2 + sum3);
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
    if (blocks > 384) {
        blocks = 384;
    }
    sum_abs<<<blocks, 256>>>((const float*)x, (float*)out, n);
}
