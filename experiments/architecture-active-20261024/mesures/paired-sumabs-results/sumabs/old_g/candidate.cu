#include <cuda_runtime.h>
#include <stdint.h>
#include <stddef.h>
#include <math.h>
#include <cub/block/block_reduce.cuh>

namespace {
constexpr int kThreads = 512;
constexpr size_t kElementsPerBlock = 4096;
constexpr size_t kMaxBlocks = 4096;

__global__ void sum_abs_vectorized(const float* x, float* y, int n, int prefix) {
    using BlockReduce = cub::BlockReduce<float, kThreads>;
    __shared__ typename BlockReduce::TempStorage storage;

    const size_t vector_count = (static_cast<size_t>(n) - static_cast<size_t>(prefix)) / 4;
    const size_t first_vector = static_cast<size_t>(blockIdx.x) * blockDim.x + threadIdx.x;
    const size_t vector_stride = static_cast<size_t>(blockDim.x) * gridDim.x;
    const size_t vector_step = vector_stride * 2;
    const float4* aligned_x = reinterpret_cast<const float4*>(x + prefix);

    float s0 = 0.0f;
    float s1 = 0.0f;
    float s2 = 0.0f;
    float s3 = 0.0f;
    float s4 = 0.0f;
    float s5 = 0.0f;
    float s6 = 0.0f;
    float s7 = 0.0f;

    for (size_t i = first_vector; i < vector_count; i += vector_step) {
        const float4 v0 = aligned_x[i];
        s0 += fabsf(v0.x);
        s1 += fabsf(v0.y);
        s2 += fabsf(v0.z);
        s3 += fabsf(v0.w);

        const size_t second = i + vector_stride;
        if (second < vector_count) {
            const float4 v1 = aligned_x[second];
            s4 += fabsf(v1.x);
            s5 += fabsf(v1.y);
            s6 += fabsf(v1.z);
            s7 += fabsf(v1.w);
        }
    }

    if (blockIdx.x == 0 && threadIdx.x == 0) {
        for (int i = 0; i < prefix; ++i) {
            s0 += fabsf(x[i]);
        }
        const size_t tail = static_cast<size_t>(prefix) + vector_count * 4;
        for (size_t i = tail; i < static_cast<size_t>(n); ++i) {
            s0 += fabsf(x[i]);
        }
    }

    const float local = ((s0 + s1) + (s2 + s3)) + ((s4 + s5) + (s6 + s7));
    const float total = BlockReduce(storage).Sum(local);
    if (threadIdx.x == 0) {
        atomicAdd(y, total);
    }
}
}

extern "C" void run(const void* x, const void*, const void*, void* out,
                    void*, int n, int, int, int) {
    cudaMemsetAsync(out, 0, sizeof(float));
    if (n <= 0) {
        return;
    }

    const uintptr_t misalignment = reinterpret_cast<uintptr_t>(x) & static_cast<uintptr_t>(15);
    int prefix = static_cast<int>(((static_cast<uintptr_t>(16) - misalignment) & static_cast<uintptr_t>(15)) / sizeof(float));
    if (prefix > n) {
        prefix = n;
    }

    size_t blocks = (static_cast<size_t>(n) + kElementsPerBlock - 1) / kElementsPerBlock;
    if (blocks > kMaxBlocks) {
        blocks = kMaxBlocks;
    }
    if (blocks == 0) {
        blocks = 1;
    }

    sum_abs_vectorized<<<static_cast<unsigned int>(blocks), kThreads>>>(
        static_cast<const float*>(x), static_cast<float*>(out), n, prefix);
}
