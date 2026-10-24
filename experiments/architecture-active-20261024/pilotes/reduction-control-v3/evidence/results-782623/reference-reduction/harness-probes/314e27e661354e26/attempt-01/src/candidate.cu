#include <cuda_runtime.h>

namespace {
constexpr int kThreads = 128;
constexpr int kTileSize = 8192;

__global__ void reduce_one_tile(const int* input, int* output, int n)
{
    __shared__ long long sums[kThreads];
    const unsigned int tid = threadIdx.x;
    long long sum = 0;

    for (int i = static_cast<int>(tid); i < n; i += blockDim.x) {
        sum += static_cast<long long>(input[i]);
    }
    sums[tid] = sum;
    __syncthreads();

    for (unsigned int stride = blockDim.x / 2; stride > 0; stride >>= 1) {
        if (tid < stride) {
            sums[tid] += sums[tid + stride];
        }
        __syncthreads();
    }

    if (tid == 0) {
        output[0] = static_cast<int>(sums[0]);
    }
}

__global__ void reduce_tiles(const int* input, long long* partials, int n)
{
    __shared__ long long sums[kThreads];
    const unsigned int tid = threadIdx.x;
    const long long base = static_cast<long long>(blockIdx.x) * kTileSize;
    long long sum = 0;

    for (int i = static_cast<int>(tid); i < kTileSize; i += blockDim.x) {
        const long long index = base + i;
        if (index < n) {
            sum += static_cast<long long>(input[index]);
        }
    }
    sums[tid] = sum;
    __syncthreads();

    for (unsigned int stride = blockDim.x / 2; stride > 0; stride >>= 1) {
        if (tid < stride) {
            sums[tid] += sums[tid + stride];
        }
        __syncthreads();
    }

    if (tid == 0) {
        partials[blockIdx.x] = sums[0];
    }
}

__global__ void finalize_partials(const long long* partials, int count, int* output)
{
    __shared__ long long sums[kThreads];
    const unsigned int tid = threadIdx.x;
    long long sum = 0;

    for (int i = static_cast<int>(tid); i < count; i += blockDim.x) {
        sum += partials[i];
    }
    sums[tid] = sum;
    __syncthreads();

    for (unsigned int stride = blockDim.x / 2; stride > 0; stride >>= 1) {
        if (tid < stride) {
            sums[tid] += sums[tid + stride];
        }
        __syncthreads();
    }

    if (tid == 0) {
        output[0] = static_cast<int>(sums[0]);
    }
}
} // namespace

extern "C" void run(const void* x, const void* k, const void* gy, void* out,
                     void* scratch, int n, int h, int l, int ks)
{
    (void)k;
    (void)gy;
    (void)h;
    (void)l;
    (void)ks;

    if (n == 0) {
        cudaMemsetAsync(out, 0, sizeof(int));
        return;
    }

    if (n == 1) {
        cudaMemcpyAsync(out, x, sizeof(int), cudaMemcpyDeviceToDevice);
        return;
    }

    const int* input = static_cast<const int*>(x);
    int* output = static_cast<int*>(out);

    if (n <= kTileSize) {
        reduce_one_tile<<<1, kThreads>>>(input, output, n);
        return;
    }

    const int partialCount = n / kTileSize + ((n % kTileSize) != 0);
    long long* partials = static_cast<long long*>(scratch);
    reduce_tiles<<<partialCount, kThreads>>>(input, partials, n);
    finalize_partials<<<1, kThreads>>>(partials, partialCount, output);
}
