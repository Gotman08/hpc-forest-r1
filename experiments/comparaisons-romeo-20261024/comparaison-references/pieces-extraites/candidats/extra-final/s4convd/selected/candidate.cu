#include <cuda_runtime.h>

__global__ void dwconv1d_fwd_bwd_input_fused_flat(
    const float* x,
    const float* k,
    const float* gy,
    float* y,
    float* gx,
    int H,
    int L,
    int K,
    size_t total)
{
    size_t index = (size_t)blockIdx.x * (size_t)blockDim.x + (size_t)threadIdx.x;
    const size_t stride = (size_t)gridDim.x * (size_t)blockDim.x;
    const int half = K / 2;

    for (; index < total; ) {
        const size_t row = index / (size_t)L;
        const int t = (int)(index - row * (size_t)L);
        const int h_index = (int)(row % (size_t)H);
        const size_t base = row * (size_t)L;
        const size_t kbase = (size_t)h_index * (size_t)K;
        float fwd_acc = 0.0f;
        float gx_acc = 0.0f;

        for (int j = 0; j < K; ++j) {
            const long long pos = (long long)t + (long long)j - (long long)half;
            if (pos >= 0 && pos < (long long)L) {
                const size_t input_index = base + (size_t)pos;
                fwd_acc += x[input_index] * k[kbase + (size_t)j];
                gx_acc += gy[input_index] * k[kbase + (size_t)(K - 1 - j)];
            }
        }

        y[index] = fwd_acc;
        gx[index] = gx_acc;

        if (total - index <= stride) {
            break;
        }
        index += stride;
    }
}

__global__ void dwconv1d_bwd_kernel_parallel(
    const float* gy,
    const float* x,
    float* gk,
    int B,
    int H,
    int L,
    int K)
{
    const int h = (int)blockIdx.y;
    const int j = (int)blockIdx.x;

    if (h >= H || j >= K) return;

    const size_t total = (size_t)B * (size_t)L;
    size_t q = (size_t)threadIdx.x;
    float acc = 0.0f;
    const int half = K / 2;

    for (; q < total; q += (size_t)blockDim.x) {
        const int b = (int)(q / (size_t)L);
        const int t = (int)(q % (size_t)L);
        const size_t base = ((size_t)b * (size_t)H + (size_t)h) * (size_t)L;
        const long long xi = (long long)t + (long long)j - (long long)half;
        if (xi >= 0 && xi < (long long)L) {
            acc += gy[base + (size_t)t] * x[base + (size_t)xi];
        }
    }

    __shared__ float partials[256];
    const int tid = (int)threadIdx.x;
    partials[tid] = acc;
    __syncthreads();

    for (int stride = (int)blockDim.x / 2; stride > 0; stride >>= 1) {
        if (tid < stride) {
            partials[tid] += partials[tid + stride];
        }
        __syncthreads();
    }

    if (tid == 0) {
        gk[(size_t)h * (size_t)K + (size_t)j] = partials[0];
    }
}

extern "C" void run(const void* x, const void* k, const void* gy, void* out, void* scratch, int n, int h, int l, int ks)
{
    const size_t size = (size_t)n * (size_t)h * (size_t)l;
    float* y = (float*)out;
    float* gx = y + size;
    float* gk = gx + size;

    if (size != 0) {
        const size_t block_count = size / 256u + (size % 256u != 0u);
        const unsigned int blocks = block_count > 65535u ? 65535u : (unsigned int)block_count;
        dwconv1d_fwd_bwd_input_fused_flat<<<blocks, 256>>>(
            (const float*)x, (const float*)k, (const float*)gy, y, gx, h, l, ks, size);
    }

    if (h > 0 && ks > 0) {
        dwconv1d_bwd_kernel_parallel<<<dim3(ks, h, 1), 256>>>(
            (const float*)gy, (const float*)x, gk, n, h, l, ks);
    }
}
