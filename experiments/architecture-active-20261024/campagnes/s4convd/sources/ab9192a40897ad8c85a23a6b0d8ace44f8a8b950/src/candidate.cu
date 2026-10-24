#include <cuda_runtime.h>

extern "C" {

__global__ void dwconv1d_fwd_naive(
    const float* x,   // [B,H,L]
    const float* k,   // [H,K]
    float* y,         // [B,H,L]
    int B, int H, int L, int K)
{
    int b = (int)blockIdx.z;
    int h = (int)blockIdx.y * (int)blockDim.y + (int)threadIdx.y;
    int t = (int)blockIdx.x * 256 + (int)threadIdx.x;

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
    int h = (int)blockIdx.y * (int)blockDim.y + (int)threadIdx.y;
    int t = (int)blockIdx.x * 256 + (int)threadIdx.x;

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

__global__ void dwconv1d_bwd_kernel_naive(
    const float* gy, // [B,H,L]
    const float* x,  // [B,H,L]
    float* gk,       // [H,K]
    int B, int H, int L, int K)
{
    int h   = (int)blockIdx.y;
    int j_i = (int)blockIdx.x * (int)blockDim.x + (int)threadIdx.x;

    if (h >= H || j_i >= K) return;

    int half = K / 2;
    float acc = 0.0f;

    for (int b = 0; b < B; ++b) {
        int base = (b * H + h) * L;
        for (int t = 0; t < L; ++t) {
            int xi = t + j_i - half;
            if (xi >= 0 && xi < L) {
                acc += gy[base + t] * x[base + xi];
            }
        }
    }

    gk[h * K + j_i] = acc;
}

}
extern "C" void run(const void*x,const void*k,const void*gy,void*out,void*scratch,int n,int h,int l,int ks)
{
    size_t size = size_t(n) * h * l;
    float* y = (float*)out;
    float* gx = y + size;
    float* gk = gx + size;

    int row_width = (l > 0 && l < 256) ? l : 256;
    int rows_per_block = 256 / row_width;
    int x_blocks = l / 256 + ((l % 256) != 0);
    int h_blocks = h / rows_per_block + ((h % rows_per_block) != 0);
    dim3 block((unsigned)row_width, (unsigned)rows_per_block, 1);
    dim3 grid((unsigned)x_blocks, (unsigned)h_blocks, (unsigned)n);

    dwconv1d_fwd_naive<<<grid, block>>>((const float*)x, (const float*)k, y, n, h, l, ks);
    dwconv1d_bwd_input_naive<<<grid, block>>>((const float*)gy, (const float*)k, gx, n, h, l, ks);
    dwconv1d_bwd_kernel_naive<<<dim3((ks + 255) / 256, h, 1), 256>>>((const float*)gy, (const float*)x, gk, n, h, l, ks);
}
