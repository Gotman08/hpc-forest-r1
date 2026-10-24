struct Particle {
    float x, y, z;
    float vx, vy, vz;
    float mass;
};

extern "C" __global__ void nbody_step_naive(const Particle* in, Particle* out, int n, float dt) {
    const int warp_width = 32;
    const int warps_per_block = static_cast<int>(blockDim.x) / warp_width;
    const int warp_in_block = static_cast<int>(threadIdx.x) / warp_width;
    const int lane = static_cast<int>(threadIdx.x) & (warp_width - 1);
    const int i = static_cast<int>(blockIdx.x) * warps_per_block + warp_in_block;

    const float G = 1.0f;
    const float softening = 0.001f;
    const unsigned int warp_mask = 0xffffffffu;

    float fx = 0.0f;
    float fy = 0.0f;
    float fz = 0.0f;

    if (i < n) {
        const Particle target = in[i];
        for (long long j = lane; j < static_cast<long long>(n); j += warp_width) {
            if (j == i) continue;

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
    }

    for (int offset = warp_width / 2; offset > 0; offset >>= 1) {
        fx += __shfl_down_sync(warp_mask, fx, offset);
        fy += __shfl_down_sync(warp_mask, fy, offset);
        fz += __shfl_down_sync(warp_mask, fz, offset);
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
