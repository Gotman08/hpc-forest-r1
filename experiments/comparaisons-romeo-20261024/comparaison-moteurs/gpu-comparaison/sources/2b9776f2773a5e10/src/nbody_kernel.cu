// Structure "Array of Structures" (AoS) used for the particle state.
struct Particle {
    float x, y, z;
    float vx, vy, vz;
    float mass;
};

// Compact shared-memory record: force evaluation needs only position and mass.
struct SourceParticle {
    float x, y, z, mass;
};

extern "C" __global__ void nbody_step_naive(const Particle* in, Particle* out, int n, float dt) {
    const int lane = threadIdx.x;
    const int i = blockIdx.x * blockDim.x + lane;
    const bool target_valid = i < n;

    const float G = 1.0f;
    const float softening = 0.001f;
    Particle target;
    float fx = 0.0f;
    float fy = 0.0f;
    float fz = 0.0f;

    if (target_valid) {
        target = in[i];
    }

    extern __shared__ SourceParticle source_tile[];

    // Every lane helps stage sources, including lanes without an output target.
    // The start barrier protects source reads; an end barrier is only needed
    // when another tile will overwrite the shared-memory buffer.
    int tile_start = 0;
    while (tile_start < n) {
        const int remaining = n - tile_start;
        const int tile_count = remaining < blockDim.x ? remaining : blockDim.x;

        if (lane < tile_count) {
            const Particle source = in[tile_start + lane];
            source_tile[lane] = {source.x, source.y, source.z, source.mass};
        }
        __syncthreads();

        if (target_valid) {
            for (int k = 0; k < tile_count; ++k) {
                const int j = tile_start + k;
                if (i == j) continue;

                const SourceParticle source = source_tile[k];
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

        const bool has_next_tile = remaining > tile_count;
        if (has_next_tile) {
            __syncthreads();
        }
        tile_start += tile_count;
    }

    if (!target_valid) return;

    Particle p = target;
    p.vx += (fx / p.mass) * dt;
    p.vy += (fy / p.mass) * dt;
    p.vz += (fz / p.mass) * dt;

    p.x += p.vx * dt;
    p.y += p.vy * dt;
    p.z += p.vz * dt;

    out[i] = p;
}
