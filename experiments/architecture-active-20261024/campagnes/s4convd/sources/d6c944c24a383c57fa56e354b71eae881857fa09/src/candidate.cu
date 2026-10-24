#include <cuda_runtime.h>

extern "C" {

__global__ void dwconv1d_fwd_input_fused(
    const float* x,   // [B,H,L]
    const float* k,   // [H,K]
    const float* gy,  // [B,H,L]
    float* y,         // [B,H,L]
    float* gx,        // [B,H,L]
    int B, int H, int L, int K,
    int use_shared)
{
    int b = (int)blockIdx.z;
    int h = (int)blockIdx.y;
    int t = (int)blockIdx.x * (int)blockDim.x + (int)threadIdx.x;
    int half = K / 2;
    int base = (b * H + h) * L;

    if (use_shared) {
        size_t tile_len = (size_t)blockDim.x + (size_t)(K - 1);
        extern __shared__ float shared[];
        float* tile_x = shared;
        float* tile_gy = tile_x + tile_len;
        float* tile_k = tile_gy + tile_len;
        int block_start = (int)blockIdx.x * (int)blockDim.x;

        for (size_t q = (size_t)threadIdx.x; q < tile_len; q += (size_t)blockDim.x) {
            long long spatial = (long long)block_start - (long long)half + (long long)q;
            float xv = 0.0f;
            float gv = 0.0f;
            if (b >= 0 && b < B && h >= 0 && h < H && spatial >= 0 && spatial < L) {
                int index = base + (int)spatial;
                xv = x[index];
                gv = gy[index];
            }
            tile_x[q] = xv;
            tile_gy[q] = gv;
        }
        for (size_t q = (size_t)threadIdx.x; q < (size_t)K; q += (size_t)blockDim.x) {
            tile_k[q] = (h >= 0 && h < H) ? k[h * K + (int)q] : 0.0f;
        }
        __syncthreads();

        if (b >= 0 && b < B && h >= 0 && h < H && t >= 0 && t < L) {
            float acc_y = 0.0f;
            float acc_gx = 0.0f;
            for (int j = 0; j < K; ++j) {
                size_t sample = (size_t)threadIdx.x + (size_t)j;
                acc_y += tile_x[sample] * tile_k[j];
                acc_gx += tile_gy[sample] * tile_k[K - 1 - j];
            }
            y[base + t] = acc_y;
            gx[base + t] = acc_gx;
        }
    } else if (b >= 0 && b < B && h >= 0 && h < H && t >= 0 && t < L) {
        float acc_y = 0.0f;
        float acc_gx = 0.0f;
        for (int j = 0; j < K; ++j) {
            int sample = t + (j - half);
            if (sample >= 0 && sample < L) {
                acc_y += x[base + sample] * k[h * K + j];
                acc_gx += gy[base + sample] * k[h * K + (K - 1 - j)];
            }
        }
        y[base + t] = acc_y;
        gx[base + t] = acc_gx;
    }
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

extern "C" void run(const void* x, const void* k, const void* gy, void* out, void* scratch, int n, int h, int l, int ks)
{
    size_t size = (size_t)n * (size_t)h * (size_t)l;
    float* y = (float*)out;
    float* gx = y + size;
    float* gk = gx + size;

    size_t shared_bytes = 0;
    int use_shared = 0;
    if (ks > 0) {
        size_t tile_len = (size_t)256 + (size_t)ks - 1;
        size_t required = (2 * tile_len + (size_t)ks) * sizeof(float);
        if (required <= (size_t)8192) {
            shared_bytes = required;
            use_shared = 1;
        }
    }

    dim3 grid((l + 255) / 256, h, n);
    dwconv1d_fwd_input_fused<<<grid, 256, shared_bytes>>>(
        (const float*)x, (const float*)k, (const float*)gy,
        y, gx, n, h, l, ks, use_shared);
    dwconv1d_bwd_kernel_naive<<<dim3((ks + 255) / 256, h, 1), 256>>>(
        (const float*)gy, (const float*)x, gk, n, h, l, ks);
}
