struct Particle {
    float x, y, z;
    float vx, vy, vz;
    float mass;
};

extern "C" __global__ void nbody_step_naive(const Particle* in, Particle* out, int n, float dt) {
    const int i = blockIdx.x * blockDim.x + threadIdx.x;
    const int lane = threadIdx.x & 31;
    const bool target_valid = i < n;

    // A complete warp can return only when none of its lanes owns a target.
    if (i - lane >= n) return;

    Particle target = {};
    if (target_valid) target = in[i];

    const float G = 1.0f;
    const float softening = 0.001f;
    float fx = 0.0f;
    float fy = 0.0f;
    float fz = 0.0f;

    // Each lane loads one source; shuffles broadcast it to the warp's targets.
    // The final tile only broadcasts its valid sources.
    int source_base = 0;
    while (source_base < n) {
        const int remaining = n - source_base;
        const int tile_count = remaining < 32 ? remaining : 32;

        float sx = 0.0f;
        float sy = 0.0f;
        float sz = 0.0f;
        float sm = 0.0f;
        if (lane < tile_count) {
            const Particle source = in[source_base + lane];
            sx = source.x;
            sy = source.y;
            sz = source.z;
            sm = source.mass;
        }

        for (int k = 0; k < tile_count; ++k) {
            const float source_x = __shfl_sync(0xffffffffu, sx, k);
            const float source_y = __shfl_sync(0xffffffffu, sy, k);
            const float source_z = __shfl_sync(0xffffffffu, sz, k);
            const float source_mass = __shfl_sync(0xffffffffu, sm, k);
            const int j = source_base + k;

            if (target_valid && i != j) {
                const float dx = source_x - target.x;
                const float dy = source_y - target.y;
                const float dz = source_z - target.z;
                const float distSq = dx * dx + dy * dy + dz * dz + softening;
                const float dist = sqrtf(distSq);
                const float f = (G * target.mass * source_mass) / (distSq * dist);

                fx += f * dx;
                fy += f * dy;
                fz += f * dz;
            }
        }
        source_base += tile_count;
    }

    if (target_valid) {
        target.vx += (fx / target.mass) * dt;
        target.vy += (fy / target.mass) * dt;
        target.vz += (fz / target.mass) * dt;

        target.x += target.vx * dt;
        target.y += target.vy * dt;
        target.z += target.vz * dt;

        out[i] = target;
    }
}
