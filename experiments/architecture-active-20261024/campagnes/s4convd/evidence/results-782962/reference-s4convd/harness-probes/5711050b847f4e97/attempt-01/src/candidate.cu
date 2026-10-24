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

__global__ void dwconv1d_bwd_kernel_cta_tiled_j(
    const float* gy, // [B,H,L]
    const float* x,  // [B,H,L]
    float* gk,       // [H,K]
    int B, int H, int L, int K)
{
    int h = (int)blockIdx.y;
    int j_base = (int)blockIdx.x * 4;
    if (h >= H || j_base >= K) return;

    int tx = (int)threadIdx.x;
    int ty = (int)threadIdx.y;
    int tid = ty * (int)blockDim.x + tx;
    int thread_count = (int)blockDim.x * (int)blockDim.y;
    int half = K / 2;

    float acc[4] = {0.0f, 0.0f, 0.0f, 0.0f};
    for (size_t b = (size_t)ty; b < (size_t)B; b += (size_t)blockDim.y) {
        size_t base = (b * (size_t)H + (size_t)h) * (size_t)L;
        for (size_t t = (size_t)tx; t < (size_t)L; t += (size_t)blockDim.x) {
            float gy_value = gy[base + t];
            #pragma unroll
            for (int q = 0; q < 4; ++q) {
                int j = j_base + q;
                if (j < K) {
                    long long xi = (long long)t + (long long)j - (long long)half;
                    if (xi >= 0 && xi < (long long)L) {
                        acc[q] += gy_value * x[base + (size_t)xi];
                    }
                }
            }
        }
    }

    __shared__ float partial[4][256];
    #pragma unroll
    for (int q = 0; q < 4; ++q) {
        partial[q][tid] = acc[q];
    }
    __syncthreads();

    int active = thread_count;
    while (active > 1) {
        int next = (active + 1) / 2;
        if (tid < active - next) {
            #pragma unroll
            for (int q = 0; q < 4; ++q) {
                partial[q][tid] += partial[q][tid + next];
            }
        }
        __syncthreads();
        active = next;
    }

    if (tid == 0) {
        #pragma unroll
        for (int q = 0; q < 4; ++q) {
            int j = j_base + q;
            if (j < K) {
                gk[(size_t)h * (size_t)K + (size_t)j] = partial[q][0];
            }
        }
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

    int row_width = (l > 0 && l < 256) ? l : 256;
    int rows_per_block = 256 / row_width;
    int x_blocks = l / 256 + ((l % 256) != 0);
    int h_blocks = h / rows_per_block + ((h % rows_per_block) != 0);
    dim3 block((unsigned)row_width, (unsigned)rows_per_block, 1);
    dim3 grid((unsigned)x_blocks, (unsigned)h_blocks, (unsigned)n);
    int j_tiles = ks / 4 + (ks % 4 != 0);

    dwconv1d_fwd_naive<<<grid, block>>>(
        (const float*)x, (const float*)k, y, n, h, l, ks);
    dwconv1d_bwd_input_naive<<<grid, block>>>(
        (const float*)gy, (const float*)k, gx, n, h, l, ks);
    dwconv1d_bwd_kernel_cta_tiled_j<<<dim3(j_tiles, h, 1), dim3(32, 8, 1)>>>(
        (const float*)gy, (const float*)x, gk, n, h, l, ks);
}
