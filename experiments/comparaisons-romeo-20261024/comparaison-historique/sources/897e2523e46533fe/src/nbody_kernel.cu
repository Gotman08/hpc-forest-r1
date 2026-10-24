struct Particle {
    float x, y, z;
    float vx, vy, vz;
    float mass;
};

extern "C" __global__ void nbody_step_naive(const Particle* in, Particle* out, int n, float dt) {
    const int lane = threadIdx.x & 31;
    const int warp = threadIdx.x >> 5;
    const int warps_per_block = blockDim.x >> 5;
    const int i = blockIdx.x * warps_per_block + warp;

    // Every lane in a warp owns the same output particle.
    if (i >= n) return;

    const Particle target = in[i];
    const float G = 1.0f;
    const float softening = 0.001f;
    float fx = 0.0f;
    float fy = 0.0f;
    float fz = 0.0f;

    // Lanes cover disjoint source indices; the loop also handles source tails.
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

    // Reduce the three force components within the warp.
    for (int offset = 16; offset > 0; offset >>= 1) {
        fx += __shfl_down_sync(0xffffffffu, fx, offset);
        fy += __shfl_down_sync(0xffffffffu, fy, offset);
        fz += __shfl_down_sync(0xffffffffu, fz, offset);
    }

    if (lane == 0) {
        Particle p = target;
        p.vx += (fx / p.mass) * dt;
        p.vy += (fy / p.mass) * dt;
        p.vz += (fz / p.mass) * dt;

        p.x += p.vx * dt;
        p.y += p.vy * dt;
        p.z += p.vz * dt;
        out[i] = p;
    }
}
