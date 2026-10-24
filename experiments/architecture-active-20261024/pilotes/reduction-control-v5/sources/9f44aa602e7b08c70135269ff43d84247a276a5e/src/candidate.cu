#include <cuda_runtime.h>
#include <stddef.h>

__global__ void reduce_tiles_4096(const int *input, int *output, int n)
{
    __shared__ int partial[256];

    const unsigned int tid = threadIdx.x;
    const size_t block_start = static_cast<size_t>(blockIdx.x) * blockDim.x * 16u;
    int sum = 0;

    #pragma unroll
    for (int i = 0; i < 16; ++i) {
        const size_t index = block_start + static_cast<size_t>(i) * blockDim.x + tid;
        if (index < static_cast<size_t>(n)) {
            sum += input[index];
        }
    }

    partial[tid] = sum;
    __syncthreads();

    for (unsigned int offset = blockDim.x / 2; offset > 0; offset >>= 1) {
        if (tid < offset) {
            partial[tid] += partial[tid + offset];
        }
        __syncthreads();
    }

    if (tid == 0) {
        output[blockIdx.x] = partial[0];
    }
}

__global__ void sum_partials_one_block(const int *input, int *output, int n)
{
    __shared__ int partial[256];

    const unsigned int tid = threadIdx.x;
    int sum = 0;
    for (size_t index = tid; index < static_cast<size_t>(n); index += blockDim.x) {
        sum += input[index];
    }

    partial[tid] = sum;
    __syncthreads();

    for (unsigned int offset = blockDim.x / 2; offset > 0; offset >>= 1) {
        if (tid < offset) {
            partial[tid] += partial[tid + offset];
        }
        __syncthreads();
    }

    if (tid == 0) {
        output[0] = partial[0];
    }
}

extern "C" void run(const void *x, const void *k, const void *gy, void *out,
                    void *scratch, int n, int h, int l, int ks)
{
    (void)k;
    (void)gy;
    (void)h;
    (void)l;
    (void)ks;

    const int *input = static_cast<const int *>(x);
    int *output = static_cast<int *>(out);

    if (n <= 1) {
        cudaMemcpyAsync(output, input, sizeof(int), cudaMemcpyDeviceToDevice);
        return;
    }

    const int blocks = n / 4096 + ((n % 4096) != 0);
    int *partials = static_cast<int *>(scratch);
    int *first_pass_output = (blocks == 1) ? output : partials;

    reduce_tiles_4096<<<blocks, 256>>>(input, first_pass_output, n);
    if (blocks > 1) {
        sum_partials_one_block<<<1, 256>>>(partials, output, blocks);
    }
}
