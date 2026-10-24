#include <cuda_runtime.h>

extern "C" {

__global__ void dwconv1d_fwd_mapped(
    const float* x,   // [B,H,L]
    const float* k,   // [H,K]
    float* y,         // [B,H,L]
    int B, int H, int L, int K)
{
    int b = (int)blockIdx.z;
    int rows_per_block = (int)blockDim.y;
    int h = (int)blockIdx.y * rows_per_block + (int)threadIdx.y;

    if (b >= B || h >= H) return;

    int first_t;
    int step;
    if (L <= 32) {
        first_t = (int)threadIdx.x;
        step = L;
    } else if (L <= 64) {
        first_t = (int)threadIdx.x;
        step = 32;
    } else {
        first_t = (int)blockIdx.x * (int)blockDim.x + (int)threadIdx.x;
        step = (int)blockDim.x;
    }

    int half = K / 2;
    int base = (b * H + h) * L;

    for (int t = first_t; t < L; t += step) {
        float acc = 0.0f;
        for (int j = 0; j < K; ++j) {
            int xi = t + j - half;
            if (xi >= 0 && xi < L) {
                acc += x[base + xi] * k[h * K + j];
            }
        }
        y[base + t] = acc;
    }
}

__global__ void dwconv1d_bwd_input_mapped(
    const float* gy,   // [B,H,L]
    const float* k,    // [H,K]
    float* gx,         // [B,H,L]
    int B, int H, int L, int K)
{
    int b = (int)blockIdx.z;
    int rows_per_block = (int)blockDim.y;
    int h = (int)blockIdx.y * rows_per_block + (int)threadIdx.y;

    if (b >= B || h >= H) return;

    int first_t;
    int step;
    if (L <= 32) {
        first_t = (int)threadIdx.x;
        step = L;
    } else if (L <= 64) {
        first_t = (int)threadIdx.x;
        step = 32;
    } else {
        first_t = (int)blockIdx.x * (int)blockDim.x + (int)threadIdx.x;
        step = (int)blockDim.x;
    }

    int half = K / 2;
    int base = (b * H + h) * L;

    for (int t = first_t; t < L; t += step) {
        float acc = 0.0f;
        for (int j = 0; j < K; ++j) {
            int gi = t + (j - half);
            if (gi >= 0 && gi < L) {
                acc += gy[base + gi] * k[h * K + (K - 1 - j)];
            }
        }
        gx[base + t] = acc;
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

extern "C" void run(const void* x, const void* k, const void* gy, void* out,
                    void* scratch, int n, int h, int l, int ks)
{
    size_t size = size_t(n) * h * l;
    float* y = (float*)out;
    float* gx = y + size;
    float* gk = gx + size;

    if (n > 0 && h > 0 && l > 0) {
        dim3 grid(1, 1, 1);
        dim3 block(1, 1, 1);

        if (l <= 32) {
            int rows_per_block = 256 / l;
            block = dim3(l, rows_per_block, 1);
            grid = dim3(1, (h + rows_per_block - 1) / rows_per_block, n);
        } else if (l <= 64) {
            block = dim3(32, 4, 1);
            grid = dim3(1, (h + 3) / 4, n);
        } else {
            block = dim3(256, 1, 1);
            grid = dim3((l + 255) / 256, h, n);
        }

        dwconv1d_fwd_mapped<<<grid, block>>>(
            (const float*)x, (const float*)k, y, n, h, l, ks);
        dwconv1d_bwd_input_mapped<<<grid, block>>>(
            (const float*)gy, (const float*)k, gx, n, h, l, ks);
    }

    if (h > 0 && ks > 0) {
        dwconv1d_bwd_kernel_naive<<<dim3((ks + 255) / 256, h, 1), 256>>>(
            (const float*)gy, (const float*)x, gk, n, h, l, ks);
    }
}
