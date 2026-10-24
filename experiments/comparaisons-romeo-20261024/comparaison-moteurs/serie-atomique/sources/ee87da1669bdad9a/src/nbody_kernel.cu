struct Particle {
    float x, y, z;
    float vx, vy, vz;
    float mass;
};

extern "C" __global__ void nbody_step_naive(const Particle* in, Particle* out, int n, float dt) {
    const int lane = threadIdx.x & 31;
    const int warps_per_block = blockDim.x / 32;
    const int warp_in_block = threadIdx.x / 32;
    const int i = blockIdx.x * warps_per_block + warp_in_block;

    const float G = 1.0f;
    const float softening = 0.001f;

    float fx = 0.0f;
    float fy = 0.0f;
    float fz = 0.0f;

    // Each warp owns one target; its lanes traverse disjoint source indices.
    if (i < n) {
        const float target_x = in[i].x;
        const float target_y = in[i].y;
        const float target_z = in[i].z;
        const float target_mass = in[i].mass;

        for (int j = lane; j < n; j += 32) {
            if (i == j) continue;

            const float dx = in[j].x - target_x;
            const float dy = in[j].y - target_y;
            const float dz = in[j].z - target_z;

            const float distSq = dx * dx + dy * dy + dz * dz + softening;
            const float invDist = rsqrtf(distSq);
            const float invDistCubed = (invDist * invDist) * invDist;
            const float f = (G * target_mass * in[j].mass) * invDistCubed;

            fx += f * dx;
            fy += f * dy;
            fz += f * dz;
        }
    }

    // No lane returns early, so every lane in each full warp reaches the reduction.
    const unsigned int full_warp_mask = 0xffffffffu;
    for (int offset = 16; offset > 0; offset >>= 1) {
        fx += __shfl_down_sync(full_warp_mask, fx, offset);
        fy += __shfl_down_sync(full_warp_mask, fy, offset);
        fz += __shfl_down_sync(full_warp_mask, fz, offset);
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
