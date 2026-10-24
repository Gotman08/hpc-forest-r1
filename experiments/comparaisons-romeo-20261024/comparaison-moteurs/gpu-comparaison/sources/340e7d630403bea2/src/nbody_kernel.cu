struct Particle {
    float x, y, z;
    float vx, vy, vz;
    float mass;
};

struct SourceParticle {
    float x, y, z, mass;
};

extern "C" __global__ void nbody_step_naive(const Particle* in, Particle* out, int n, float dt) {
    const int i = blockIdx.x * blockDim.x + threadIdx.x;
    const bool active = i < n;

    const float G = 1.0f;
    const float softening = 0.001f;

    float fx = 0.0f;
    float fy = 0.0f;
    float fz = 0.0f;

    Particle target;
    if (active) {
        target = in[i];
    }

    extern __shared__ SourceParticle source_tile[];

    for (int tile_start = 0; tile_start < n;) {
        const int remaining = n - tile_start;
        const int tile_count = remaining < blockDim.x ? remaining : blockDim.x;
        const int lane = threadIdx.x;

        if (lane < tile_count) {
            const Particle source = in[tile_start + lane];
            source_tile[lane].x = source.x;
            source_tile[lane].y = source.y;
            source_tile[lane].z = source.z;
            source_tile[lane].mass = source.mass;
        }
        __syncthreads();

        if (active) {
            for (int offset = 0; offset < tile_count; ++offset) {
                const int j = tile_start + offset;
                if (i == j) continue;

                const SourceParticle source = source_tile[offset];
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
        tile_start += tile_count;
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
