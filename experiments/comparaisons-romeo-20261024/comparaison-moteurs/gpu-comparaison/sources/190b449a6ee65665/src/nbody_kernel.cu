struct Particle {
    float x, y, z;
    float vx, vy, vz;
    float mass;
};

extern "C" __global__ void nbody_step_naive(const Particle* in, Particle* out, int n, float dt) {
    const int warp_width = 32;
    const int warps_per_block = blockDim.x / warp_width;
    const int warp_index = static_cast<int>(threadIdx.x) / warp_width;
    const int lane = static_cast<int>(threadIdx.x) % warp_width;
    const int target = static_cast<int>(blockIdx.x) * warps_per_block + warp_index;

    // All lanes in a warp share target, so an inactive target exits uniformly.
    if (target >= n) return;

    const Particle target_particle = in[target];
    const float softening = 0.001f;
    float fx = 0.0f;
    float fy = 0.0f;
    float fz = 0.0f;

    // Each lane accumulates source indices separated by one warp width.
    for (int j = lane; j < n;) {
        if (j != target) {
            const Particle source = in[j];
            const float dx = source.x - target_particle.x;
            const float dy = source.y - target_particle.y;
            const float dz = source.z - target_particle.z;
            const float distSq = dx * dx + dy * dy + dz * dz + softening;
            const float dist = sqrtf(distSq);
            const float f = (target_particle.mass * source.mass) / (distSq * dist);

            fx += f * dx;
            fy += f * dy;
            fz += f * dz;
        }

        // Avoid signed overflow when advancing the final source index.
        if (n - j <= warp_width) break;
        j += warp_width;
    }

    // Every lane of a valid warp participates in all three reductions.
    const unsigned int mask = 0xffffffffu;
    fx += __shfl_down_sync(mask, fx, 16);
    fy += __shfl_down_sync(mask, fy, 16);
    fz += __shfl_down_sync(mask, fz, 16);
    fx += __shfl_down_sync(mask, fx, 8);
    fy += __shfl_down_sync(mask, fy, 8);
    fz += __shfl_down_sync(mask, fz, 8);
    fx += __shfl_down_sync(mask, fx, 4);
    fy += __shfl_down_sync(mask, fy, 4);
    fz += __shfl_down_sync(mask, fz, 4);
    fx += __shfl_down_sync(mask, fx, 2);
    fy += __shfl_down_sync(mask, fy, 2);
    fz += __shfl_down_sync(mask, fz, 2);
    fx += __shfl_down_sync(mask, fx, 1);
    fy += __shfl_down_sync(mask, fy, 1);
    fz += __shfl_down_sync(mask, fz, 1);

    if (lane == 0) {
        Particle p = target_particle;
        p.vx += (fx / p.mass) * dt;
        p.vy += (fy / p.mass) * dt;
        p.vz += (fz / p.mass) * dt;
        p.x += p.vx * dt;
        p.y += p.vy * dt;
        p.z += p.vz * dt;
        out[target] = p;
    }
}
