#include <cuda_runtime.h>

#include <stdint.h>

extern "C" {

#define WARP 32
#define MAX_L 48
#define MAX_K 47

// Tune these 3
#define BWDK_BTILE 64
#define BWDK_KPACK 4
#define BWDK_BLOCK 128


__device__ __forceinline__ float warp_reduce_sum(float val) {
    for (int offset = 16; offset > 0; offset >>= 1) {
        val += __shfl_down_sync(0xffffffff, val, offset);
    }
    return val;
}



// Forward specialized for L <= 48, K <= 48
// one warp per (b,h)
// grid.x -> B
// grid.y -> H
// block.x = 32

__global__ void dwconv1d_fwd_smallL(
    const float* __restrict__ x,      // [B,H,L]
    const float* __restrict__ kHK,    // [H,K]
    float* __restrict__ y,            // [B,H,L]
    const int B,
    const int H,
    const int L,
    const int K)
{
    const int lane = threadIdx.x;
    const int b = blockIdx.x;
    const int h = blockIdx.y;
    const int pad = K >> 1;

    if (b >= B || h >= H || lane >= WARP) return;
    if (L > MAX_L || K > MAX_K) return;

    __shared__ float sx[MAX_L];
    __shared__ float sk[MAX_K];

    const float* xb = x + ((size_t)b * H + h) * L;
    const float* kb = kHK + (size_t)h * K;
    float* yb = y + ((size_t)b * H + h) * L;

    for (int i = lane; i < L; i += WARP) {
        sx[i] = xb[i];
    }
    for (int i = lane; i < K; i += WARP) {
        sk[i] = kb[i];
    }
    __syncthreads();

    int t0 = lane;
    if (t0 < L) {
        float acc = 0.0f;
        #pragma unroll
        for (int kk = 0; kk < MAX_K; ++kk) {
            if (kk < K) {
                int xi = t0 + kk - pad;
                if ((unsigned)xi < (unsigned)L) {
                    acc = fmaf(sx[xi], sk[kk], acc);
                }
            }
        }
        yb[t0] = acc;
    }

    int t1 = lane + WARP;
    if (t1 < L) {
        float acc = 0.0f;
        #pragma unroll
        for (int kk = 0; kk < MAX_K; ++kk) {
            if (kk < K) {
                int xi = t1 + kk - pad;
                if ((unsigned)xi < (unsigned)L) {
                    acc = fmaf(sx[xi], sk[kk], acc);
                }
            }
        }
        yb[t1] = acc;
    }
}



// Backward input specialized
// gx[b,h,t] = sum_k gy[b,h,t-k+pad] * k[h,k]
// one warp per (b,h)

__global__ void dwconv1d_bwd_input_smallL(
    const float* __restrict__ gy,     // [B,H,L]
    const float* __restrict__ kHK,    // [H,K]
    float* __restrict__ gx,           // [B,H,L]
    const int B,
    const int H,
    const int L,
    const int K)
{
    const int lane = threadIdx.x;
    const int b = blockIdx.x;
    const int h = blockIdx.y;
    const int pad = K >> 1;

    if (b >= B || h >= H || lane >= WARP) return;
    if (L > MAX_L || K > MAX_K) return;

    __shared__ float sgy[MAX_L];
    __shared__ float sk[MAX_K];

    const float* gy_bh = gy + ((size_t)b * H + h) * L;
    const float* k_h   = kHK + (size_t)h * K;
    float* gx_bh       = gx + ((size_t)b * H + h) * L;

    for (int i = lane; i < L; i += WARP) {
        sgy[i] = gy_bh[i];
    }
    for (int i = lane; i < K; i += WARP) {
        sk[i] = k_h[i];
    }
    __syncthreads();

    int t0 = lane;
    if (t0 < L) {
        float acc = 0.0f;
        #pragma unroll
        for (int kk = 0; kk < MAX_K; ++kk) {
            if (kk < K) {
                int tout = t0 - kk + pad;
                if ((unsigned)tout < (unsigned)L) {
                    acc = fmaf(sgy[tout], sk[kk], acc);
                }
            }
        }
        gx_bh[t0] = acc;
    }

    int t1 = lane + WARP;
    if (t1 < L) {
        float acc = 0.0f;
        #pragma unroll
        for (int kk = 0; kk < MAX_K; ++kk) {
            if (kk < K) {
                int tout = t1 - kk + pad;
                if ((unsigned)tout < (unsigned)L) {
                    acc = fmaf(sgy[tout], sk[kk], acc);
                }
            }
        }
        gx_bh[t1] = acc;
    }
}



// Backward weight, redesigned
//
// grid.x -> H
// grid.y -> num_btiles
// block.x = BWDK_BLOCK
//
// Each block handles:
//   - one channel h
//   - one batch tile
//
// It stages [btile, L] of x and gy into shared memory,
// computes multiple taps (KPACK=4) at a time,
// does warp-level reduction,
// then atomicAdd into gk[h, k].
//
// This removes:
//   - partials tensor
//   - second reduction kernel

__global__ void dwconv1d_bwd_weight_atomic_packed_smallL(
    const float* __restrict__ gy,     // [B,H,L]
    const float* __restrict__ x,      // [B,H,L]
    float* __restrict__ gk,           // [H,K]
    const int B,
    const int H,
    const int L,
    const int K,
    const int num_btiles)
{
    const int tid  = threadIdx.x;
    const int lane = tid & 31;
    const int wid  = tid >> 5;
    const int nwarps = BWDK_BLOCK / 32;

    const int h = blockIdx.x;
    const int btile = blockIdx.y;
    const int pad = K >> 1;

    if (h >= H || btile >= num_btiles) return;
    if (L > MAX_L || K > MAX_K) return;

    const int b_start = btile * BWDK_BTILE;
    const int b_count = min(BWDK_BTILE, B - b_start);
    if (b_count <= 0) return;

    __shared__ float sGY[BWDK_BTILE][MAX_L];
    __shared__ float sX [BWDK_BTILE][MAX_L];

    // one shared slot per warp, per packed tap
    __shared__ float sWarpSums[BWDK_KPACK][BWDK_BLOCK / 32];

    
    // Stage x and gy for this batch tile
    
    for (int linear = tid; linear < b_count * L; linear += BWDK_BLOCK) {
        const int bb = linear / L;
        const int t  = linear - bb * L;

        const size_t base = ((size_t)(b_start + bb) * H + h) * L;
        sGY[bb][t] = gy[base + t];
        sX [bb][t] = x [base + t];
    }
    __syncthreads();

    
    
    for (int k0 = 0; k0 < K; k0 += BWDK_KPACK) {
        float acc0 = 0.0f;
        float acc1 = 0.0f;
        float acc2 = 0.0f;
        float acc3 = 0.0f;

        for (int linear = tid; linear < b_count * L; linear += BWDK_BLOCK) {
            const int bb = linear / L;
            const int t  = linear - bb * L;

            const float gyv = sGY[bb][t];

            const int j0 = k0 + 0;
            const int j1 = k0 + 1;
            const int j2 = k0 + 2;
            const int j3 = k0 + 3;

            if (j0 < K) {
                const int xi = t + j0 - pad;
                if ((unsigned)xi < (unsigned)L) {
                    acc0 = fmaf(gyv, sX[bb][xi], acc0);
                }
            }
            if (j1 < K) {
                const int xi = t + j1 - pad;
                if ((unsigned)xi < (unsigned)L) {
                    acc1 = fmaf(gyv, sX[bb][xi], acc1);
                }
            }
            if (j2 < K) {
                const int xi = t + j2 - pad;
                if ((unsigned)xi < (unsigned)L) {
                    acc2 = fmaf(gyv, sX[bb][xi], acc2);
                }
            }
            if (j3 < K) {
                const int xi = t + j3 - pad;
                if ((unsigned)xi < (unsigned)L) {
                    acc3 = fmaf(gyv, sX[bb][xi], acc3);
                }
            }
        }

        // Warp-level reduce
        acc0 = warp_reduce_sum(acc0);
        acc1 = warp_reduce_sum(acc1);
        acc2 = warp_reduce_sum(acc2);
        acc3 = warp_reduce_sum(acc3);

        if (lane == 0) {
            sWarpSums[0][wid] = acc0;
            sWarpSums[1][wid] = acc1;
            sWarpSums[2][wid] = acc2;
            sWarpSums[3][wid] = acc3;
        }
        __syncthreads();

        // Final reduce by warp 0
        if (wid == 0) {
            float v0 = (lane < nwarps) ? sWarpSums[0][lane] : 0.0f;
            float v1 = (lane < nwarps) ? sWarpSums[1][lane] : 0.0f;
            float v2 = (lane < nwarps) ? sWarpSums[2][lane] : 0.0f;
            float v3 = (lane < nwarps) ? sWarpSums[3][lane] : 0.0f;

            v0 = warp_reduce_sum(v0);
            v1 = warp_reduce_sum(v1);
            v2 = warp_reduce_sum(v2);
            v3 = warp_reduce_sum(v3);

            if (lane == 0) {
                if (k0 + 0 < K) atomicAdd(&gk[h * K + (k0 + 0)], v0);
                if (k0 + 1 < K) atomicAdd(&gk[h * K + (k0 + 1)], v1);
                if (k0 + 2 < K) atomicAdd(&gk[h * K + (k0 + 2)], v2);
                if (k0 + 3 < K) atomicAdd(&gk[h * K + (k0 + 3)], v3);
            }
        }
        __syncthreads();
    }
}

} // extern "C"
extern "C" void run(const void*x,const void*k,const void*gy,void*out,void*scratch,int n,int h,int l,int ks)
{size_t size=size_t(n)*h*l;float*y=(float*)out;float*gx=y+size;float*gk=gx+size;
cudaMemsetAsync(gk,0,size_t(h)*ks*4);
dwconv1d_fwd_smallL<<<dim3(n,h),32>>>((const float*)x,(const float*)k,y,n,h,l,ks);
dwconv1d_bwd_input_smallL<<<dim3(n,h),32>>>((const float*)gy,(const float*)k,gx,n,h,l,ks);
dwconv1d_bwd_weight_atomic_packed_smallL<<<dim3(h,(n+63)/64),128>>>((const float*)gy,(const float*)x,gk,n,h,l,ks,(n+63)/64);}
