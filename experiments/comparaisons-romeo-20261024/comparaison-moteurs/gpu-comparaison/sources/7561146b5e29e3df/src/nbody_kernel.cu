struct Particle {
    float x, y, z;
    float vx, vy, vz;
    float mass;
};

extern "C" __global__ void nbody_step_naive(const Particle* in, Particle* out, int n, float dt) {
    constexpr int TILE_SIZE = 256;

    const int i = static_cast<int>(blockIdx.x * blockDim.x + threadIdx.x);
    const bool active = i < n;

    Particle target;
    if (active) {
        target = in[i];
    }

    const float G = 1.0f;
    const float softening = 0.001f;
    float fx = 0.0f;
    float fy = 0.0f;
    float fz = 0.0f;

    extern __shared__ Particle source_tile[];

    for (int tile_start = 0; tile_start < n;) {
        const int remaining = n - tile_start;
        const int tile_count = remaining < TILE_SIZE ? remaining : TILE_SIZE;

        for (int source_offset = static_cast<int>(threadIdx.x);
             source_offset < tile_count;
             source_offset += static_cast<int>(blockDim.x)) {
            source_tile[source_offset] = in[tile_start + source_offset];
        }
        __syncthreads();

        if (active) {
            for (int source_offset = 0; source_offset < tile_count; ++source_offset) {
                const int j = tile_start + source_offset;
                if (i == j) continue;

                const Particle source = source_tile[source_offset];
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

        tile_start += tile_count;
        __syncthreads();
    }

    if (!active) return;

    Particle p = target;
    p.vx += (fx / p.mass) * dt;
    p.vy += (fy / p.mass) * dt;
    p.vz += (fz / p.mass) * dt;

    p.x += p.vx * dt;
    p.y += p.vy * dt;
    p.z += p.vz * dt;

    out[i] = p;
}
