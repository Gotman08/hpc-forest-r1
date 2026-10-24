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
    int b = (int)blockIdx.z;
    int h = (int)blockIdx.y;
    int t = (int)blockIdx.x * (int)blockDim.x + (int)threadIdx.x;

    if (b >= B || h >= H || t >= L) return;

    int half = K / 2;
    int base = (b * H + h) * L;
    const float* filter = k + h * K;

    float y_acc = 0.0f;
    float gx_acc = 0.0f;
    for (int j = 0; j < K; ++j) {
        int xi = t + j - half;
        if (xi >= 0 && xi < L) {
            y_acc += x[base + xi] * filter[j];
            gx_acc += gy[base + xi] * filter[K - 1 - j];
        }
    }

    y[base + t] = y_acc;
    gx[base + t] = gx_acc;
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
extern "C" void run(const void*x,const void*k,const void*gy,void*out,void*scratch,int n,int h,int l,int ks)
{size_t size=size_t(n)*h*l;float*y=(float*)out;float*gx=y+size;float*gk=gx+size;
dwconv1d_fwd_bwd_input_fused<<<dim3((l+255)/256,h,n),256>>>((const float*)x,(const float*)k,(const float*)gy,y,gx,n,h,l,ks);
dwconv1d_bwd_kernel_naive<<<dim3((ks+255)/256,h,1),256>>>((const float*)gy,(const float*)x,gk,n,h,l,ks);}
