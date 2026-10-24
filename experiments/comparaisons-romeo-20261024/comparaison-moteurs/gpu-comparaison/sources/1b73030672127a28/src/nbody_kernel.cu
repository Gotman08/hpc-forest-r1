struct Particle {
    float x, y, z;
    float vx, vy, vz;
    float mass;
};

extern "C" __global__ void nbody_step_naive(const Particle* in, Particle* out, int n, float dt) {
    extern __shared__ Particle source_tile[];

    const int tile_size = static_cast<int>(blockDim.x);
    const int lane = static_cast<int>(threadIdx.x);
    const int i = static_cast<int>(blockIdx.x) * tile_size + lane;
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

    for (int tile_start = 0; tile_start < n; tile_start += tile_size) {
        const int source_index = tile_start + lane;
        if (source_index < n) {
            source_tile[lane] = in[source_index];
        }
        __syncthreads();

        const int remaining = n - tile_start;
        const int tile_count = remaining < tile_size ? remaining : tile_size;
        if (active) {
            for (int offset = 0; offset < tile_count; ++offset) {
                const int j = tile_start + offset;
                if (i == j) continue;

                const Particle source = source_tile[offset];
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
        __syncthreads();
    }

    if (!active) return;

    target.vx += (fx / target.mass) * dt;
    target.vy += (fy / target.mass) * dt;
    target.vz += (fz / target.mass) * dt;

    target.x += target.vx * dt;
    target.y += target.vy * dt;
    target.z += target.vz * dt;

    out[i] = target;
}
