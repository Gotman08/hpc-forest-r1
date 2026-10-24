#include <cuda_runtime.h>

static constexpr int kBlockSize = 256;
static constexpr int GK_TILE_SIZE = 16384;
static constexpr int GK_TAPS_PER_CTA = 16;

static unsigned int flat_grid_blocks(size_t count)
{
    size_t blocks = count / kBlockSize + (count % kBlockSize != 0);
    if (blocks > 0x7fffffffULL) blocks = 0x7fffffffULL;
    return (unsigned int)blocks;
}

extern "C" {

__global__ void dwconv1d_fwd_flat4(
    const float* x,
    const float* k,
    float* y,
    int H, int L, int K,
    size_t total)
{
    size_t idx = (size_t)blockIdx.x * blockDim.x + threadIdx.x;
    const size_t stride = (size_t)gridDim.x * blockDim.x;
    const long long half = (long long)K / 2;

    while (idx < total) {
        const size_t row = idx / (size_t)L;
        const int t = (int)(idx - row * (size_t)L);
        const int h = (int)(row % (size_t)H);
        const size_t base = row * (size_t)L;
        const size_t coeff_base = (size_t)h * (size_t)K;

        long long j_begin = half - t;
        if (j_begin < 0) j_begin = 0;
        long long j_end = (long long)L + half - t;
        if (j_end < 0) j_end = 0;
        if (j_end > K) j_end = K;
        if (j_begin > j_end) j_begin = j_end;

        float acc0 = 0.0f;
        float acc1 = 0.0f;
        float acc2 = 0.0f;
        float acc3 = 0.0f;
        long long j = j_begin;

        for (; j_end - j >= 4; j += 4) {
            const size_t x0 = base + (size_t)((long long)t + j - half);
            const size_t x1 = base + (size_t)((long long)t + j + 1 - half);
            const size_t x2 = base + (size_t)((long long)t + j + 2 - half);
            const size_t x3 = base + (size_t)((long long)t + j + 3 - half);
            acc0 += x[x0] * k[coeff_base + (size_t)j];
            acc1 += x[x1] * k[coeff_base + (size_t)(j + 1)];
            acc2 += x[x2] * k[coeff_base + (size_t)(j + 2)];
            acc3 += x[x3] * k[coeff_base + (size_t)(j + 3)];
        }
        for (; j < j_end; ++j) {
            const size_t xi = base + (size_t)((long long)t + j - half);
            acc0 += x[xi] * k[coeff_base + (size_t)j];
        }

        y[idx] = ((acc0 + acc1) + acc2) + acc3;

        if (total - idx <= stride) break;
        idx += stride;
    }
}

__global__ void dwconv1d_bwd_input_flat4(
    const float* gy,
    const float* k,
    float* gx,
    int H, int L, int K,
    size_t total)
{
    size_t idx = (size_t)blockIdx.x * blockDim.x + threadIdx.x;
    const size_t stride = (size_t)gridDim.x * blockDim.x;
    const long long half = (long long)K / 2;

    while (idx < total) {
        const size_t row = idx / (size_t)L;
        const int t = (int)(idx - row * (size_t)L);
        const int h = (int)(row % (size_t)H);
        const size_t base = row * (size_t)L;
        const size_t coeff_base = (size_t)h * (size_t)K;

        long long j_begin = (long long)t + half - L + 1;
        if (j_begin < 0) j_begin = 0;
        long long j_end = (long long)t + half + 1;
        if (j_end > K) j_end = K;
        if (j_begin > j_end) j_begin = j_end;

        float acc0 = 0.0f;
        float acc1 = 0.0f;
        float acc2 = 0.0f;
        float acc3 = 0.0f;
        long long j = j_begin;

        for (; j_end - j >= 4; j += 4) {
            const size_t g0 = base + (size_t)((long long)t - j + half);
            const size_t g1 = base + (size_t)((long long)t - j - 1 + half);
            const size_t g2 = base + (size_t)((long long)t - j - 2 + half);
            const size_t g3 = base + (size_t)((long long)t - j - 3 + half);
            acc0 += gy[g0] * k[coeff_base + (size_t)j];
            acc1 += gy[g1] * k[coeff_base + (size_t)(j + 1)];
            acc2 += gy[g2] * k[coeff_base + (size_t)(j + 2)];
            acc3 += gy[g3] * k[coeff_base + (size_t)(j + 3)];
        }
        for (; j < j_end; ++j) {
            const size_t gi = base + (size_t)((long long)t - j + half);
            acc0 += gy[gi] * k[coeff_base + (size_t)j];
        }

        gx[idx] = ((acc0 + acc1) + acc2) + acc3;

        if (total - idx <= stride) break;
        idx += stride;
    }
}

__global__ void dwconv1d_bwd_kernel_partials(
    const float* gy,
    const float* x,
    float* partial,
    int B, int H, int L, int K,
    int tile_count, int group_count)
{
    const int tid = (int)threadIdx.x;
    const size_t flat_block = (size_t)blockIdx.x;
    const int group = (int)(flat_block % (size_t)group_count);
    const size_t h_and_tile = flat_block / (size_t)group_count;
    const int h = (int)(h_and_tile % (size_t)H);
    const int tile = (int)(h_and_tile / (size_t)H);
    if (tile >= tile_count) return;

    const size_t total = (size_t)B * (size_t)L;
    const size_t tile_start = (size_t)tile * (size_t)GK_TILE_SIZE;
    size_t tile_end = tile_start + (size_t)GK_TILE_SIZE;
    if (tile_end > total) tile_end = total;

    const int j0 = group * GK_TAPS_PER_CTA;
    int group_len = K - j0;
    if (group_len > GK_TAPS_PER_CTA) group_len = GK_TAPS_PER_CTA;

    const int half = K / 2;
    const size_t q0 = tile_start + (size_t)tid;
    int b = (int)(q0 / (size_t)L);
    int t = (int)(q0 - (size_t)b * (size_t)L);
    const int row_advance = (int)blockDim.x / L;
    const int col_advance = (int)blockDim.x % L;

    float accum[GK_TAPS_PER_CTA] = {0.0f};
    for (size_t q = q0; q < tile_end; q += (size_t)blockDim.x) {
        const size_t row_base = ((size_t)b * (size_t)H + (size_t)h) * (size_t)L;
        const float gy_value = gy[row_base + (size_t)t];

        #pragma unroll
        for (int m = 0; m < GK_TAPS_PER_CTA; ++m) {
            if (m < group_len) {
                const int j = j0 + m;
                const int xi = t + j - half;
                if (xi >= 0 && xi < L) {
                    accum[m] += gy_value * x[row_base + (size_t)xi];
                }
            }
        }

        b += row_advance;
        t += col_advance;
        if (t >= L) {
            t -= L;
            ++b;
        }
    }

    __shared__ float tree[GK_TAPS_PER_CTA][256];
    for (int m = 0; m < group_len; ++m) {
        tree[m][tid] = accum[m];
    }
    __syncthreads();

    for (int stride = (int)blockDim.x / 2; stride > 0; stride >>= 1) {
        if (tid < stride) {
            for (int m = 0; m < group_len; ++m) {
                tree[m][tid] += tree[m][tid + stride];
            }
        }
        __syncthreads();
    }

    if (tid == 0) {
        const size_t output_count = (size_t)H * (size_t)K;
        for (int m = 0; m < group_len; ++m) {
            const int j = j0 + m;
            partial[(size_t)tile * output_count + (size_t)h * (size_t)K + (size_t)j] = tree[m][0];
        }
    }
}

__global__ void dwconv1d_bwd_kernel_finalize(
    const float* partial,
    float* gk,
    size_t output_count,
    int tile_count)
{
    const size_t output = (size_t)blockIdx.x * (size_t)blockDim.x + (size_t)threadIdx.x;
    if (output >= output_count) return;

    float sum = 0.0f;
    for (int tile = 0; tile < tile_count; ++tile) {
        sum += partial[(size_t)tile * output_count + output];
    }
    gk[output] = sum;
}

}

extern "C" void run(const void* x, const void* k, const void* gy, void* out, void* scratch,
                     int n, int h, int l, int ks)
{
    const size_t size = (size_t)n * (size_t)h * (size_t)l;
    float* y = (float*)out;
    float* gx = y + size;
    float* gk = gx + size;

    if (size != 0) {
        const unsigned int blocks = flat_grid_blocks(size);
        dwconv1d_fwd_flat4<<<blocks, kBlockSize>>>(
            (const float*)x, (const float*)k, y, h, l, ks, size);
        dwconv1d_bwd_input_flat4<<<blocks, kBlockSize>>>(
            (const float*)gy, (const float*)k, gx, h, l, ks, size);
    }

    const size_t total = (size_t)n * (size_t)l;
    const size_t output_count = (size_t)h * (size_t)ks;
    if (output_count != 0) {
        const int tile_count = (int)(total / (size_t)GK_TILE_SIZE +
            (total % (size_t)GK_TILE_SIZE != 0));
        if (tile_count > 0) {
            const int group_count = ks / GK_TAPS_PER_CTA +
                (ks % GK_TAPS_PER_CTA != 0);
            const size_t producer_blocks =
                (size_t)tile_count * (size_t)h * (size_t)group_count;
            dwconv1d_bwd_kernel_partials<<<dim3((unsigned int)producer_blocks, 1, 1), 256>>>(
                (const float*)gy, (const float*)x, (float*)scratch,
                n, h, l, ks, tile_count, group_count);
        }

        const unsigned int final_blocks = (unsigned int)((output_count + 255) / 256);
        dwconv1d_bwd_kernel_finalize<<<dim3(final_blocks, 1, 1), 256>>>(
            (const float*)scratch, gk, output_count, tile_count);
    }
}
