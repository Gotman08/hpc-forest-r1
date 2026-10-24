#include <cuda_runtime.h>

extern "C" {

__global__ void dwconv1d_fwd_input_fused(
    const float* x,
    const float* k,
    const float* gy,
    float* y,
    float* gx,
    int B, int H, int L, int K,
    int use_shared)
{
    int b = (int)blockIdx.z;
    int h = (int)blockIdx.y;
    size_t t = (size_t)blockIdx.x * (size_t)blockDim.x + (size_t)threadIdx.x;
    int half = K / 2;
    size_t base = ((size_t)b * (size_t)H + (size_t)h) * (size_t)L;

    if (use_shared) {
        size_t tile_len = (size_t)blockDim.x + (size_t)(K - 1);
        extern __shared__ float shared[];
        float* tile_x = shared;
        float* tile_gy = tile_x + tile_len;
        float* tile_k = tile_gy + tile_len;
        size_t block_start = (size_t)blockIdx.x * (size_t)blockDim.x;

        for (size_t q = (size_t)threadIdx.x; q < tile_len; q += (size_t)blockDim.x) {
            long long spatial = (long long)block_start - (long long)half + (long long)q;
            float xv = 0.0f;
            float gv = 0.0f;
            if (b < B && h < H && spatial >= 0 && spatial < (long long)L) {
                size_t index = base + (size_t)spatial;
                xv = x[index];
                gv = gy[index];
            }
            tile_x[q] = xv;
            tile_gy[q] = gv;
        }
        for (size_t q = (size_t)threadIdx.x; q < (size_t)K; q += (size_t)blockDim.x) {
            tile_k[q] = (h < H) ? k[(size_t)h * (size_t)K + q] : 0.0f;
        }
        __syncthreads();

        if (b < B && h < H && t < (size_t)L) {
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
    } else if (b < B && h < H && t < (size_t)L) {
        float acc_y = 0.0f;
        float acc_gx = 0.0f;
        for (int j = 0; j < K; ++j) {
            long long sample = (long long)t + (long long)j - (long long)half;
            if (sample >= 0 && sample < (long long)L) {
                size_t index = base + (size_t)sample;
                acc_y += x[index] * k[(size_t)h * (size_t)K + (size_t)j];
                acc_gx += gy[index] * k[(size_t)h * (size_t)K + (size_t)(K - 1 - j)];
            }
        }
        y[base + t] = acc_y;
        gx[base + t] = acc_gx;
    }
}

__global__ void dwconv1d_bwd_kernel_cta_tiled_j(
    const float* gy,
    const float* x,
    float* gk,
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
    if (n < 0 || h < 0 || l < 0 || ks < 0) return;

    size_t size = (size_t)n * (size_t)h * (size_t)l;
    float* y = (float*)out;
    float* gx = y + size;
    float* gk = gx + size;

    if (n > 0 && h > 0 && l > 0) {
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

        int x_blocks = l / 256 + ((l % 256) != 0);
        dim3 grid((unsigned)x_blocks, (unsigned)h, (unsigned)n);
        dwconv1d_fwd_input_fused<<<grid, 256, shared_bytes>>>(
            (const float*)x, (const float*)k, (const float*)gy,
            y, gx, n, h, l, ks, use_shared);
    }

    if (h > 0 && ks > 0) {
        int j_tiles = ks / 4 + ((ks % 4) != 0);
        dwconv1d_bwd_kernel_cta_tiled_j<<<dim3((unsigned)j_tiles, (unsigned)h, 1), dim3(32, 8, 1)>>>(
            (const float*)gy, (const float*)x, gk, n, h, l, ks);
    }
}
