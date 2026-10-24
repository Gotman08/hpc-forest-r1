#include <cuda_runtime.h>

extern "C" {

__global__ void dwconv1d_fwd_naive(
    const float* x,
    const float* k,
    float* y,
    int B, int H, int L, int K)
{
    const int b = (int)blockIdx.z;
    int h;
    int t0;
    int tstep;

    if (L <= 32) {
        const int rows_per_cta = 256 / L;
        h = (int)blockIdx.y * rows_per_cta + (int)threadIdx.y;
        t0 = (int)threadIdx.x;
        tstep = L;
    } else if (L <= 64) {
        h = (int)blockIdx.y * 8 + ((int)threadIdx.x >> 5);
        t0 = (int)threadIdx.x & 31;
        tstep = 32;
    } else {
        h = (int)blockIdx.y;
        t0 = (int)blockIdx.x * (int)blockDim.x + (int)threadIdx.x;
        tstep = L;
    }

    if (b >= B || h >= H) return;

    const int half = K / 2;
    const int base = (b * H + h) * L;
    for (int t = t0; t < L; t += tstep) {
        float acc = 0.0f;
        for (int j = 0; j < K; ++j) {
            const int xi = t + j - half;
            if (xi >= 0 && xi < L) {
                acc += x[base + xi] * k[h * K + j];
            }
        }
        y[base + t] = acc;
    }
}

__global__ void dwconv1d_bwd_input_naive(
    const float* gy,
    const float* k,
    float* gx,
    int B, int H, int L, int K)
{
    const int b = (int)blockIdx.z;
    int h;
    int t0;
    int tstep;

    if (L <= 32) {
        const int rows_per_cta = 256 / L;
        h = (int)blockIdx.y * rows_per_cta + (int)threadIdx.y;
        t0 = (int)threadIdx.x;
        tstep = L;
    } else if (L <= 64) {
        h = (int)blockIdx.y * 8 + ((int)threadIdx.x >> 5);
        t0 = (int)threadIdx.x & 31;
        tstep = 32;
    } else {
        h = (int)blockIdx.y;
        t0 = (int)blockIdx.x * (int)blockDim.x + (int)threadIdx.x;
        tstep = L;
    }

    if (b >= B || h >= H) return;

    const int half = K / 2;
    const int base = (b * H + h) * L;
    for (int t = t0; t < L; t += tstep) {
        float acc = 0.0f;
        for (int j = 0; j < K; ++j) {
            const int gi = t + (j - half);
            if (gi >= 0 && gi < L) {
                acc += gy[base + gi] * k[h * K + (K - 1 - j)];
            }
        }
        gx[base + t] = acc;
    }
}

__global__ void dwconv1d_bwd_kernel_naive(
    const float* gy,
    const float* x,
    float* gk,
    int B, int H, int L, int K)
{
    const int h = (int)blockIdx.y;
    const int j_i = (int)blockIdx.x * (int)blockDim.x + (int)threadIdx.x;

    if (h >= H || j_i >= K) return;

    const int half = K / 2;
    float acc = 0.0f;

    for (int b = 0; b < B; ++b) {
        const int base = (b * H + h) * L;
        for (int t = 0; t < L; ++t) {
            const int xi = t + j_i - half;
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
    const size_t size = size_t(n) * h * l;
    float* y = (float*)out;
    float* gx = y + size;
    float* gk = gx + size;

    if (n > 0 && h > 0 && l > 0) {
        dim3 grid;
        dim3 block;
        if (l <= 32) {
            const int rows_per_cta = 256 / l;
            block = dim3(l, rows_per_cta, 1);
            grid = dim3(1, (h + rows_per_cta - 1) / rows_per_cta, n);
        } else if (l <= 64) {
            block = dim3(256, 1, 1);
            grid = dim3(1, (h + 7) / 8, n);
        } else {
            block = dim3(256, 1, 1);
            grid = dim3((l + 255) / 256, h, n);
        }

        dwconv1d_fwd_naive<<<grid, block>>>(
            (const float*)x, (const float*)k, y, n, h, l, ks);
        dwconv1d_bwd_input_naive<<<grid, block>>>(
            (const float*)gy, (const float*)k, gx, n, h, l, ks);
    }

    if (h > 0 && ks > 0) {
        dwconv1d_bwd_kernel_naive<<<dim3((ks + 255) / 256, h, 1), 256>>>(
            (const float*)gy, (const float*)x, gk, n, h, l, ks);
    }
}
