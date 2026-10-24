#include <cuda_runtime.h>

static int choose_reduction_threads(long long count)
{
    if (count >= 256) return 256;
    if (count >= 128) return 128;
    if (count >= 64) return 64;
    return 32;
}

enum { WEIGHT_PARTIAL_TILE = 65536 };

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

// Fallback and small-reduction path: one CTA reduces all B*L values per output.
__global__ void dwconv1d_bwd_kernel_direct(
    const float* gy,
    const float* x,
    float* gk,
    int B, int H, int L, int K)
{
    int h = (int)blockIdx.y;
    int j = (int)blockIdx.x;
    int tid = (int)threadIdx.x;
    long long work = (long long)B * (long long)L;
    long long half = K / 2;
    float acc = 0.0f;

    for (long long p = tid; p < work; p += (long long)blockDim.x) {
        long long b = p / L;
        long long t = p - b * L;
        long long xi = t + (long long)j - half;
        if (xi >= 0 && xi < L) {
            long long base = (b * H + h) * L;
            acc += gy[base + t] * x[base + xi];
        }
    }

    __shared__ float sums[256];
    sums[tid] = acc;
    __syncthreads();
    for (int offset = (int)blockDim.x / 2; offset > 0; offset >>= 1) {
        if (tid < offset) sums[tid] += sums[tid + offset];
        __syncthreads();
    }
    if (tid == 0) gk[(long long)h * K + j] = sums[0];
}

// Each CTA writes one FP32 partial for a (h,j) output and a B*L tile.
__global__ void dwconv1d_bwd_kernel_partials(
    const float* gy,
    const float* x,
    float* partials,
    int B, int H, int L, int K, int tile_count)
{
    int h = (int)blockIdx.y;
    int j = (int)blockIdx.x;
    int tid = (int)threadIdx.x;
    long long work = (long long)B * (long long)L;
    long long begin = (long long)blockIdx.z * WEIGHT_PARTIAL_TILE;
    long long end = begin + WEIGHT_PARTIAL_TILE;
    if (end > work) end = work;
    long long half = K / 2;
    float acc = 0.0f;

    for (long long p = begin + tid; p < end; p += (long long)blockDim.x) {
        long long b = p / L;
        long long t = p - b * L;
        long long xi = t + (long long)j - half;
        if (xi >= 0 && xi < L) {
            long long base = (b * H + h) * L;
            acc += gy[base + t] * x[base + xi];
        }
    }

    __shared__ float sums[256];
    sums[tid] = acc;
    __syncthreads();
    for (int offset = (int)blockDim.x / 2; offset > 0; offset >>= 1) {
        if (tid < offset) sums[tid] += sums[tid + offset];
        __syncthreads();
    }
    if (tid == 0) {
        long long index = ((long long)h * K + j) * tile_count + (long long)blockIdx.z;
        partials[index] = sums[0];
    }
}

// Every partial read here was written by the preceding partial-kernel launch.
__global__ void dwconv1d_bwd_kernel_finalize(
    const float* partials,
    float* gk,
    int H, int K, int tile_count)
{
    int h = (int)blockIdx.y;
    int j = (int)blockIdx.x;
    int tid = (int)threadIdx.x;
    float acc = 0.0f;

    for (int tile = tid; tile < tile_count; tile += (int)blockDim.x) {
        long long index = ((long long)h * K + j) * tile_count + tile;
        acc += partials[index];
    }

    __shared__ float sums[256];
    sums[tid] = acc;
    __syncthreads();
    for (int offset = (int)blockDim.x / 2; offset > 0; offset >>= 1) {
        if (tid < offset) sums[tid] += sums[tid + offset];
        __syncthreads();
    }
    if (tid == 0) gk[(long long)h * K + j] = sums[0];
}

}

extern "C" void run(const void* x, const void* k, const void* gy,
                    void* out, void* scratch, int n, int h, int l, int ks)
{
    if (h <= 0 || ks <= 0 || n < 0 || l < 0) return;

    size_t size = (size_t)n * (size_t)h * (size_t)l;
    float* y = (float*)out;
    float* gx = y + size;
    float* gk = gx + size;

    if (n > 0 && l > 0) {
        dwconv1d_fwd_naive<<<dim3((l + 255) / 256, h, n), 256>>>(
            (const float*)x, (const float*)k, y, n, h, l, ks);
        dwconv1d_bwd_input_naive<<<dim3((l + 255) / 256, h, n), 256>>>(
            (const float*)gy, (const float*)k, gx, n, h, l, ks);
    }

    long long work = (long long)n * (long long)l;
    long long tiles_by_size = (work + WEIGHT_PARTIAL_TILE - 1LL) / WEIGHT_PARTIAL_TILE;
    long long tiles_by_workspace = work / (long long)ks;
    long long tile_count = tiles_by_size;
    if (tile_count > tiles_by_workspace) tile_count = tiles_by_workspace;

    // The cap bounds partial storage to at most B*H*L floats. If splitting
    // cannot be used, the direct CTA path still writes every weight gradient.
    if (scratch != 0 && tile_count >= 2 && tile_count <= 65535) {
        int tiles = (int)tile_count;
        float* partials = (float*)scratch;
        dwconv1d_bwd_kernel_partials<<<dim3(ks, h, tiles), 256>>>(
            (const float*)gy, (const float*)x, partials, n, h, l, ks, tiles);
        dwconv1d_bwd_kernel_finalize<<<dim3(ks, h, 1), choose_reduction_threads(tiles)>>>(
            partials, gk, h, ks, tiles);
    } else {
        dwconv1d_bwd_kernel_direct<<<dim3(ks, h, 1), choose_reduction_threads(work)>>>(
            (const float*)gy, (const float*)x, gk, n, h, l, ks);
    }
}
