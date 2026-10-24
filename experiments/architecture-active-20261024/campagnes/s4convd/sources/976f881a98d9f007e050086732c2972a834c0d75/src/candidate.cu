#include <cuda_runtime.h>

extern "C" {

__global__ void dwconv1d_fwd_naive(
    const float* x,   // [B,H,L]
    const float* k,   // [H,K]
    float* y,         // [B,H,L]
    int B, int H, int L, int K)
{
    int b = (int)blockIdx.z;
    int h = (int)blockIdx.y;
    int t = (int)blockIdx.x * (int)blockDim.x + (int)threadIdx.x;

    if (b >= B || h >= H || t >= L) return;

    int half = K / 2;
    int base = (b * H + h) * L;

    float acc = 0.0f;
    for (int j = 0; j < K; ++j) {
        int xi = t + j - half;
        if (xi >= 0 && xi < L) {
            acc += x[base + xi] * k[h * K + j];
        }
    }
    y[base + t] = acc;
}

__global__ void dwconv1d_bwd_input_naive(
    const float* gy,   // [B,H,L]
    const float* k,    // [H,K]
    float* gx,         // [B,H,L]
    int B, int H, int L, int K)
{
    int b = (int)blockIdx.z;
    int h = (int)blockIdx.y;
    int t = (int)blockIdx.x * (int)blockDim.x + (int)threadIdx.x;

    if (b >= B || h >= H || t >= L) return;

    int half = K / 2;
    int base = (b * H + h) * L;

    float acc = 0.0f;
    for (int j = 0; j < K; ++j) {
        int gi = t + (j - half);
        if (gi >= 0 && gi < L) {
            acc += gy[base + gi] * k[h * K + (K - 1 - j)];
        }
    }
    gx[base + t] = acc;
}

__global__ void dwconv1d_bwd_kernel_cta(
    const float* gy, // [B,H,L]
    const float* x,  // [B,H,L]
    float* gk,       // [H,K]
    int B, int H, int L, int K)
{
    int h = (int)blockIdx.y;
    int j = (int)blockIdx.x;
    if (h >= H || j >= K) return;

    int tx = (int)threadIdx.x;
    int ty = (int)threadIdx.y;
    int tid = ty * (int)blockDim.x + tx;
    int thread_count = (int)blockDim.x * (int)blockDim.y;
    int half = K / 2;

    float acc = 0.0f;
    for (int b = ty; b < B; b += (int)blockDim.y) {
        int base = (b * H + h) * L;
        for (int t = tx; t < L; t += (int)blockDim.x) {
            int xi = t + j - half;
            if (xi >= 0 && xi < L) {
                acc += gy[base + t] * x[base + xi];
            }
        }
    }

    __shared__ float partial[256];
    partial[tid] = acc;
    __syncthreads();

    int active = thread_count;
    while (active > 1) {
        int next = (active + 1) / 2;
        if (tid < active - next) {
            partial[tid] += partial[tid + next];
        }
        __syncthreads();
        active = next;
    }

    if (tid == 0) {
        gk[h * K + j] = partial[0];
    }
}

}

extern "C" void run(const void* x, const void* k, const void* gy, void* out,
                    void* scratch, int n, int h, int l, int ks)
{
    size_t size = size_t(n) * h * l;
    float* y = (float*)out;
    float* gx = y + size;
    float* gk = gx + size;

    int block_x = l < 32 ? l : 32;
    int max_block_y = 256 / block_x;
    int block_y = n < max_block_y ? n : max_block_y;

    dwconv1d_fwd_naive<<<dim3((l + 255) / 256, h, n), 256>>>(
        (const float*)x, (const float*)k, y, n, h, l, ks);
    dwconv1d_bwd_input_naive<<<dim3((l + 255) / 256, h, n), 256>>>(
        (const float*)gy, (const float*)k, gx, n, h, l, ks);
    dwconv1d_bwd_kernel_cta<<<dim3(ks, h, 1), dim3(block_x, block_y, 1)>>>(
        (const float*)gy, (const float*)x, gk, n, h, l, ks);
}
