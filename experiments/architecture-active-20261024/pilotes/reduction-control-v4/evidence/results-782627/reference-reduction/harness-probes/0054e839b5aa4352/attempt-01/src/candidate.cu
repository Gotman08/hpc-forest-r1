#include <cuda_runtime.h>

namespace {
constexpr int kThreads = 128;
constexpr int kTileElements = 8192;
constexpr int kFinalizerLimit = 1024;
constexpr int kDirectLimit = 128;

__global__ void reduce_direct(const int *input, int n, int *out)
{
    __shared__ long long sums[kThreads];
    const unsigned int tid = threadIdx.x;
    long long value = 0;

    for (int i = static_cast<int>(tid); i < n; i += blockDim.x) {
        value += static_cast<long long>(input[i]);
    }
    sums[tid] = value;
    __syncthreads();

    for (unsigned int stride = 1; stride < blockDim.x; stride *= 2) {
        if ((tid % (2 * stride)) == 0) {
            sums[tid] += sums[tid + stride];
        }
        __syncthreads();
    }

    if (tid == 0) {
        *out = static_cast<int>(sums[0]);
    }
}

__global__ void write_zero(int *out)
{
    if (threadIdx.x == 0) {
        *out = 0;
    }
}

// Each CTA covers one bounded tile. Threads accumulate their strided values,
// then use the same 128-thread shared-memory reduction tree for every stage.
template <typename Input>
__global__ void reduce_tiles(const Input *input, long long *partials, int n)
{
    __shared__ long long sums[kThreads];
    const unsigned int tid = threadIdx.x;
    const long long begin = static_cast<long long>(blockIdx.x) * kTileElements + tid;
    const long long end = (static_cast<long long>(blockIdx.x) + 1LL) * kTileElements;
    long long value = 0;

    for (long long i = begin; i < end && i < n; i += blockDim.x) {
        value += static_cast<long long>(input[i]);
    }
    sums[tid] = value;
    __syncthreads();

    for (unsigned int stride = 1; stride < blockDim.x; stride *= 2) {
        if ((tid % (2 * stride)) == 0) {
            sums[tid] += sums[tid + stride];
        }
        __syncthreads();
    }

    if (tid == 0) {
        partials[blockIdx.x] = sums[0];
    }
}

__global__ void finalize_partials(const long long *partials, int count, int *out)
{
    __shared__ long long sums[kThreads];
    const unsigned int tid = threadIdx.x;
    long long value = 0;

    for (int i = static_cast<int>(tid); i < count; i += blockDim.x) {
        value += partials[i];
    }
    sums[tid] = value;
    __syncthreads();

    for (unsigned int stride = 1; stride < blockDim.x; stride *= 2) {
        if ((tid % (2 * stride)) == 0) {
            sums[tid] += sums[tid + stride];
        }
        __syncthreads();
    }

    if (tid == 0) {
        *out = static_cast<int>(sums[0]);
    }
}
} // namespace

extern "C" void run(const void *x, const void *k, const void *gy,
                     void *out, void *scratch, int n, int h, int l, int ks)
{
    (void)k;
    (void)gy;
    (void)h;
    (void)l;
    (void)ks;

    if (out == nullptr || n < 0) {
        return;
    }
    if (n == 0) {
        write_zero<<<1, 1>>>(static_cast<int *>(out));
        return;
    }
    if (x == nullptr) {
        return;
    }
    if (n <= kDirectLimit) {
        reduce_direct<<<1, kThreads>>>(static_cast<const int *>(x), n,
                                       static_cast<int *>(out));
        return;
    }
    if (scratch == nullptr) {
        return;
    }

    const int initial_count = 1 + (n - 1) / kTileElements;
    long long *buffer0 = static_cast<long long *>(scratch);
    long long *buffer1 = buffer0 + initial_count;

    reduce_tiles<int><<<initial_count, kThreads>>>(
        static_cast<const int *>(x), buffer0, n);

    const long long *current = buffer0;
    int count = initial_count;
    bool write_buffer1 = true;

    while (count > kFinalizerLimit) {
        const int next_count = 1 + (count - 1) / kTileElements;
        long long *next = write_buffer1 ? buffer1 : buffer0;
        reduce_tiles<long long><<<next_count, kThreads>>>(current, next, count);
        current = next;
        count = next_count;
        write_buffer1 = !write_buffer1;
    }

    finalize_partials<<<1, kThreads>>>(current, count, static_cast<int *>(out));
}
