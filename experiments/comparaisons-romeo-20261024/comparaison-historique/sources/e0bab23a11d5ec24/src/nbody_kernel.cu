struct Particle {
    float x, y, z;
    float vx, vy, vz;
    float mass;
};

// One warp computes the force on each output particle.
extern "C" __global__ void nbody_step_naive(const Particle* in, Particle* out, int n, float dt) {
    const int lane = threadIdx.x & 31;
    const int warp = threadIdx.x >> 5;
    const int warps_per_block = blockDim.x >> 5;
    const int i = blockIdx.x * warps_per_block + warp;
    const bool valid = i < n;

    Particle p{};
    if (valid) p = in[i];

    const float G = 1.0f;
    const float softening = 0.001f;
    float fx = 0.0f;
    float fy = 0.0f;
    float fz = 0.0f;

    // Each lane accumulates a disjoint, strided subset of the sources.
    #pragma unroll 2
    for (int j = lane; j < n; j += 32) {
        if (valid && j != i) {
            float dx = in[j].x - p.x;
            float dy = in[j].y - p.y;
            float dz = in[j].z - p.z;

            float distSq = dx * dx + dy * dy + dz * dz + softening;
            float dist = sqrtf(distSq);
            float f = (G * p.mass * in[j].mass) / (distSq * dist);

            fx += f * dx;
            fy += f * dy;
            fz += f * dz;
        }
    }

    // The configured block has complete warps, so every lane participates.
    const unsigned mask = 0xffffffffu;
    for (int offset = 16; offset > 0; offset >>= 1) {
        fx += __shfl_down_sync(mask, fx, offset);
        fy += __shfl_down_sync(mask, fy, offset);
        fz += __shfl_down_sync(mask, fz, offset);
    }

    if (lane == 0 && valid) {
        p.vx += (fx / p.mass) * dt;
        p.vy += (fy / p.mass) * dt;
        p.vz += (fz / p.mass) * dt;

        p.x += p.vx * dt;
        p.y += p.vy * dt;
        p.z += p.vz * dt;

        out[i] = p;
    }
}
