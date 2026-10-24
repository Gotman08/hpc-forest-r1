struct Particle {
    float x, y, z;
    float vx, vy, vz;
    float mass;
};

extern "C" __global__ void nbody_step_naive(const Particle* in, Particle* out, int n, float dt) {
    const int lane = threadIdx.x & 31;
    const int warp_id = threadIdx.x >> 5;
    const int warps_per_block = blockDim.x >> 5;
    const int i = blockIdx.x * warps_per_block + warp_id;

    const float G = 1.0f;
    const float softening = 0.001f;
    float fx = 0.0f;
    float fy = 0.0f;
    float fz = 0.0f;

    if (i < n) {
        const Particle target = in[i];

        // Each lane accumulates a disjoint strided subset of source particles.
        #pragma unroll 4
        for (int j = lane; j < n; j += 32) {
            if (j == i) continue;

            const float dx = in[j].x - target.x;
            const float dy = in[j].y - target.y;
            const float dz = in[j].z - target.z;

            const float distSq = dx * dx + dy * dy + dz * dz + softening;
            const float dist = sqrtf(distSq);
            const float f = (G * target.mass * in[j].mass) / (distSq * dist);

            fx += f * dx;
            fy += f * dy;
            fz += f * dz;
        }
    }

    // All lanes, including lanes for an out-of-range target warp, reach each reduction.
    const unsigned int mask = 0xffffffffu;
    for (int offset = 16; offset > 0; offset >>= 1) {
        fx += __shfl_down_sync(mask, fx, offset);
        fy += __shfl_down_sync(mask, fy, offset);
        fz += __shfl_down_sync(mask, fz, offset);
    }

    if (lane == 0 && i < n) {
        Particle p = in[i];
        p.vx += (fx / p.mass) * dt;
        p.vy += (fy / p.mass) * dt;
        p.vz += (fz / p.mass) * dt;

        p.x += p.vx * dt;
        p.y += p.vy * dt;
        p.z += p.vz * dt;

        out[i] = p;
    }
}
