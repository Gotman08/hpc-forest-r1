#include <cuda_runtime.h>

extern "C" {

__global__ void dwconv1d_fwd_input_fused_packed(
    const float* x,
    const float* k,
    const float* gy,
    float* y,
    float* gx,
    int B, int H, int L, int K,
    int use_shared)
{
    const size_t b = (size_t)blockIdx.z;
    const size_t row = (size_t)threadIdx.y;
    const size_t h = (size_t)blockIdx.y * (size_t)blockDim.y + row;
    const size_t width = (size_t)blockDim.x;
    const size_t t = (size_t)blockIdx.x * width + (size_t)threadIdx.x;
    const int half = K / 2;
    const size_t rows = (size_t)blockDim.y;

    if (use_shared) {
        const size_t tile_len = width + (size_t)(K - 1);
        const size_t tile_count = rows * tile_len;
        const size_t filter_count = rows * (size_t)K;
        const size_t tid = row * width + (size_t)threadIdx.x;
        const size_t threads = width * rows;
        const size_t x_start = (size_t)blockIdx.x * width;

        extern __shared__ float shared[];
        float* tile_x = shared;
        float* tile_gy = tile_x + tile_count;
        float* tile_k = tile_gy + tile_count;

        for (size_t q = tid; q < tile_count; q += threads) {
            const size_t row_index = q / tile_len;
            const size_t pos = q - row_index * tile_len;
            const size_t h_index = (size_t)blockIdx.y * rows + row_index;
            const long long spatial = (long long)x_start - (long long)half + (long long)pos;
            float xv = 0.0f;
            float gv = 0.0f;
            if (b < (size_t)B && h_index < (size_t)H && spatial >= 0 && spatial < (long long)L) {
                const size_t base = (b * (size_t)H + h_index) * (size_t)L;
                xv = x[base + (size_t)spatial];
                gv = gy[base + (size_t)spatial];
            }
            tile_x[q] = xv;
            tile_gy[q] = gv;
        }

        for (size_t q = tid; q < filter_count; q += threads) {
            const size_t row_index = q / (size_t)K;
            const size_t h_index = (size_t)blockIdx.y * rows + row_index;
            const size_t j = q - row_index * (size_t)K;
            tile_k[q] = (h_index < (size_t)H) ? k[h_index * (size_t)K + j] : 0.0f;
        }
        __syncthreads();

        if (b < (size_t)B && h < (size_t)H && t < (size_t)L) {
            const size_t base = (b * (size_t)H + h) * (size_t)L;
            const size_t tile_row = row * tile_len;
            float acc_y = 0.0f;
            float acc_gx = 0.0f;
            for (int j = 0; j < K; ++j) {
                const size_t sample = tile_row + (size_t)threadIdx.x + (size_t)j;
                const size_t filter_base = row * (size_t)K;
                acc_y += tile_x[sample] * tile_k[filter_base + (size_t)j];
                acc_gx += tile_gy[sample] * tile_k[filter_base + (size_t)(K - 1 - j)];
            }
            y[base + t] = acc_y;
            gx[base + t] = acc_gx;
        }
    } else if (b < (size_t)B && h < (size_t)H && t < (size_t)L) {
        const size_t base = (b * (size_t)H + h) * (size_t)L;
        const size_t filter_base = h * (size_t)K;
        float acc_y = 0.0f;
        float acc_gx = 0.0f;
        for (int j = 0; j < K; ++j) {
            const long long sample = (long long)t + (long long)j - (long long)half;
            if (sample >= 0 && sample < (long long)L) {
                const size_t index = base + (size_t)sample;
                acc_y += x[index] * k[filter_base + (size_t)j];
                acc_gx += gy[index] * k[filter_base + (size_t)(K - 1 - j)];
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
    const size_t h = (size_t)blockIdx.y;
    const size_t j_base = (size_t)blockIdx.x * 4;
    if (h >= (size_t)H || j_base >= (size_t)K) return;

    const int tx = (int)threadIdx.x;
    const int ty = (int)threadIdx.y;
    const int tid = ty * (int)blockDim.x + tx;
    const int thread_count = (int)blockDim.x * (int)blockDim.y;
    const int half = K / 2;

    float acc[4] = {0.0f, 0.0f, 0.0f, 0.0f};
    for (size_t b = (size_t)ty; b < (size_t)B; b += (size_t)blockDim.y) {
        const size_t base = (b * (size_t)H + h) * (size_t)L;
        for (size_t t = (size_t)tx; t < (size_t)L; t += (size_t)blockDim.x) {
            const float gy_value = gy[base + t];
            #pragma unroll
            for (int q = 0; q < 4; ++q) {
                const size_t j_index = j_base + (size_t)q;
                if (j_index < (size_t)K) {
                    const long long xi = (long long)t + (long long)j_index - (long long)half;
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
        const int next = (active + 1) / 2;
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
            const size_t j_index = j_base + (size_t)q;
            if (j_index < (size_t)K) {
                gk[h * (size_t)K + j_index] = partial[q][0];
            }
        }
    }
}

}

extern "C" void run(const void* x, const void* k, const void* gy, void* out,
                    void* scratch, int n, int h, int l, int ks)
{
    if (n < 0 || h < 0 || l < 0 || ks < 0) return;

    const size_t size = (size_t)n * (size_t)h * (size_t)l;
    float* y = (float*)out;
    float* gx = y + size;
    float* gk = gx + size;

    if (n > 0 && h > 0 && l > 0) {
        const int row_width = (l < 256) ? l : 256;
        const int rows_per_block = 256 / row_width;
        const int x_blocks = l / row_width + ((l % row_width) != 0);
        const int h_blocks = h / rows_per_block + ((h % rows_per_block) != 0);
        const dim3 block((unsigned)row_width, (unsigned)rows_per_block, 1);
        const dim3 grid((unsigned)x_blocks, (unsigned)h_blocks, (unsigned)n);

        size_t shared_bytes = 0;
        int use_shared = 0;
        if (ks > 0) {
            const size_t tile_len = (size_t)row_width + (size_t)ks - 1;
            const size_t tile_count = (size_t)rows_per_block * tile_len;
            const size_t filter_count = (size_t)rows_per_block * (size_t)ks;
            const size_t required = (2 * tile_count + filter_count) * sizeof(float);
            if (required <= (size_t)8192) {
                shared_bytes = required;
                use_shared = 1;
            }
        }

        dwconv1d_fwd_input_fused_packed<<<grid, block, shared_bytes>>>(
            (const float*)x, (const float*)k, (const float*)gy,
            y, gx, n, h, l, ks, use_shared);
    }

    if (h > 0 && ks > 0) {
        const int j_tiles = ks / 4 + ((ks % 4) != 0);
        dwconv1d_bwd_kernel_cta_tiled_j<<<dim3((unsigned)j_tiles, (unsigned)h, 1), dim3(32, 8, 1)>>>(
            (const float*)gy, (const float*)x, gk, n, h, l, ks);
    }
}
