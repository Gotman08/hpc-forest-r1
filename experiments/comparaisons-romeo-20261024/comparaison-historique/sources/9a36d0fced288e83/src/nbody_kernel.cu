struct Particle {
    float x, y, z;
    float vx, vy, vz;
    float mass;
};

extern "C" __global__ void nbody_step_naive(const Particle* in, Particle* out, int n, float dt) {
    constexpr int warp_width = 32;
    const int lane = threadIdx.x % warp_width;
    const int warp = threadIdx.x / warp_width;
    const int warps_per_block = blockDim.x / warp_width;
    const int i = blockIdx.x * warps_per_block + warp;
    if (i >= n) return;

    const float G = 1.0f;
    const float softening = 0.001f;
    const Particle target = in[i];

    float fx = 0.0f;
    float fy = 0.0f;
    float fz = 0.0f;

    for (int j = lane; j < n; j += warp_width) {
        if (i == j) continue;

        const Particle source = in[j];
        const float dx = source.x - target.x;
        const float dy = source.y - target.y;
        const float dz = source.z - target.z;

        const float distSq = dx * dx + dy * dy + dz * dz + softening;
        const float dist = sqrtf(distSq);
        const float f = (G * target.mass * source.mass) / (distSq * dist);

        fx += f * dx;
        fy += f * dy;
        fz += f * dz;
    }

    for (int offset = warp_width / 2; offset > 0; offset >>= 1) {
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
