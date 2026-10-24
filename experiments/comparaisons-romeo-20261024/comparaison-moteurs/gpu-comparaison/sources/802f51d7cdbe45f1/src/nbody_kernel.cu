// Structure Array of Structures for the fixed n-body interface.
struct Particle {
    float x, y, z;
    float vx, vy, vz;
    float mass;
};

// One CTA owns a target row. Its threads stride over the source dimension,
// reduce their force sums within each warp, then reduce the warp sums in warp 0.
extern "C" __global__ void nbody_step_naive(const Particle* in, Particle* out, int n, float dt) {
    const int i = static_cast<int>(blockIdx.x);
    if (i >= n) return;

    const int lane = static_cast<int>(threadIdx.x) & 31;
    const int warp = static_cast<int>(threadIdx.x) >> 5;
    const Particle target = in[i];
    const float softening = 0.001f;

    float fx = 0.0f;
    float fy = 0.0f;
    float fz = 0.0f;

    for (int j = static_cast<int>(threadIdx.x); j < n; j += static_cast<int>(blockDim.x)) {
        if (j == i) continue;

        const Particle source = in[j];
        const float dx = source.x - target.x;
        const float dy = source.y - target.y;
        const float dz = source.z - target.z;

        const float distSq = dx * dx + dy * dy + dz * dz + softening;
        const float dist = sqrtf(distSq);
        const float f = (1.0f * target.mass * source.mass) / (distSq * dist);

        fx += f * dx;
        fy += f * dy;
        fz += f * dz;
    }

    const unsigned int full_warp_mask = 0xffffffffu;
    for (int offset = 16; offset > 0; offset >>= 1) {
        fx += __shfl_down_sync(full_warp_mask, fx, offset);
        fy += __shfl_down_sync(full_warp_mask, fy, offset);
        fz += __shfl_down_sync(full_warp_mask, fz, offset);
    }

    // The selected launch uses 256 threads, i.e. eight warps per CTA.
    __shared__ float warp_fx[8];
    __shared__ float warp_fy[8];
    __shared__ float warp_fz[8];
    if (lane == 0) {
        warp_fx[warp] = fx;
        warp_fy[warp] = fy;
        warp_fz[warp] = fz;
    }
    __syncthreads();

    if (warp == 0) {
        float row_fx = lane < 8 ? warp_fx[lane] : 0.0f;
        float row_fy = lane < 8 ? warp_fy[lane] : 0.0f;
        float row_fz = lane < 8 ? warp_fz[lane] : 0.0f;

        for (int offset = 16; offset > 0; offset >>= 1) {
            row_fx += __shfl_down_sync(full_warp_mask, row_fx, offset);
            row_fy += __shfl_down_sync(full_warp_mask, row_fy, offset);
            row_fz += __shfl_down_sync(full_warp_mask, row_fz, offset);
        }

        if (lane == 0) {
            Particle p = target;
            p.vx += (row_fx / p.mass) * dt;
            p.vy += (row_fy / p.mass) * dt;
            p.vz += (row_fz / p.mass) * dt;

            p.x += p.vx * dt;
            p.y += p.vy * dt;
            p.z += p.vz * dt;

            out[i] = p;
        }
    }
}
