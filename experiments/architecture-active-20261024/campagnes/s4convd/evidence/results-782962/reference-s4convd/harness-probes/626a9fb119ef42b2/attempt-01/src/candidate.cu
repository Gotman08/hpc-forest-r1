#include <cuda_runtime.h>

extern "C" {

__global__ void dwconv1d_fwd_bwd_input_fused(
    const float* x,   // [B,H,L]
    const float* k,   // [H,K]
    const float* gy,  // [B,H,L]
    float* y,         // [B,H,L]
    float* gx,        // [B,H,L]
    int B, int H, int L, int K)
{
    const int b = (int)blockIdx.z;
    const int h = (int)blockIdx.y;
    const unsigned int tiles = ((unsigned int)L + 255u) / 256u;
    const unsigned int path = (unsigned int)blockIdx.x / tiles;
    const unsigned int tile = (unsigned int)blockIdx.x - path * tiles;
    const unsigned int t_u = tile * blockDim.x + threadIdx.x;

    if (b >= B || h >= H || t_u >= (unsigned int)L) return;

    const int t = (int)t_u;
    const int half = K / 2;
    const size_t base = ((size_t)b * (size_t)H + (size_t)h) * (size_t)L;
    const float* filter = k + (size_t)h * (size_t)K;

    // Keep the two output paths in one launch, but use separate block cohorts
    // so each thread needs only one accumulator and one input stream.
    if (path == 0u) {
        float acc = 0.0f;
        for (int j = 0; j < K; ++j) {
            const int xi = t + j - half;
            if (xi >= 0 && xi < L) {
                acc += x[base + (size_t)xi] * filter[j];
            }
        }
        y[base + (size_t)t] = acc;
    } else {
        float acc = 0.0f;
        for (int j = 0; j < K; ++j) {
            const int xi = t + j - half;
            if (xi >= 0 && xi < L) {
                acc += gy[base + (size_t)xi] * filter[K - 1 - j];
            }
        }
        gx[base + (size_t)t] = acc;
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
    const unsigned int tiles = ((unsigned int)l + 255u) / 256u;

    dwconv1d_fwd_bwd_input_fused<<<dim3(2u * tiles, h, n), 256>>>(
        (const float*)x, (const float*)k, (const float*)gy, y, gx,
        n, h, l, ks);
    dwconv1d_bwd_kernel_naive<<<dim3((ks + 255) / 256, h, 1), 256>>>(
        (const float*)gy, (const float*)x, gk, n, h, l, ks);
}
