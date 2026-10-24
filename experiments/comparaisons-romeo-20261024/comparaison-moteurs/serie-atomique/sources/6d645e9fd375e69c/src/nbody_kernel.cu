struct Particle {
    float x, y, z;
    float vx, vy, vz;
    float mass;
};

extern "C" __global__ void nbody_step_naive(const Particle* in, Particle* out, int n, float dt) {
    const int warp_width = 32;
    const int lane = threadIdx.x & (warp_width - 1);
    const int warp_in_block = threadIdx.x / warp_width;
    const int warps_per_block = blockDim.x / warp_width;

    // launch.json assigns one output particle to each warp.
    const long long output_index = (long long)blockIdx.x * warps_per_block + warp_in_block;
    if (output_index >= n) return;

    const int i = (int)output_index;
    const Particle target = in[i];
    const float G = 1.0f;
    const float softening = 0.001f;

    float fx = 0.0f;
    float fy = 0.0f;
    float fz = 0.0f;

    // Each lane accumulates a distinct strided subset of source particles.
    for (long long j = lane; j < (long long)n; j += warp_width) {
        if (j == i) continue;

        const Particle source = in[j];
        float dx = source.x - target.x;
        float dy = source.y - target.y;
        float dz = source.z - target.z;

        float distSq = dx * dx + dy * dy + dz * dz + softening;
        float dist = sqrtf(distSq);
        float f = (G * target.mass * source.mass) / (distSq * dist);

        fx += f * dx;
        fy += f * dy;
        fz += f * dz;
    }

    // Reduce the three force components within the warp.
    for (int offset = warp_width / 2; offset > 0; offset >>= 1) {
        fx += __shfl_down_sync(0xffffffffu, fx, offset);
        fy += __shfl_down_sync(0xffffffffu, fy, offset);
        fz += __shfl_down_sync(0xffffffffu, fz, offset);
    }

    // Only lane zero owns and writes this output particle.
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
