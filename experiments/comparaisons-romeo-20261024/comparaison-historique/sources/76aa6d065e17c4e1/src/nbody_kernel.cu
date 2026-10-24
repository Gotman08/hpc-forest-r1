// Structure "Array of Structures" : one particle per target thread.
struct Particle {
    float x, y, z;
    float vx, vy, vz;
    float mass;
};

// Compact shared-memory representation of fields used by the interaction.
struct SourceParticle {
    float x, y, z;
    float mass;
};

// Each block stages 512 source particles for its 256 target threads.
extern "C" __global__ void nbody_step_naive(const Particle* in, Particle* out, int n, float dt) {
    const int tid = threadIdx.x;
    const int i = blockIdx.x * blockDim.x + tid;
    const bool active = i < n;

    Particle target;
    if (active) target = in[i];

    extern __shared__ SourceParticle source_tile[];

    const float G = 1.0f;
    const float softening = 0.001f;
    const int tile_capacity = 512;

    float fx = 0.0f;
    float fy = 0.0f;
    float fz = 0.0f;

    for (int tile_base = 0; tile_base < n;) {
        int tile_count = n - tile_base;
        if (tile_count > tile_capacity) tile_count = tile_capacity;

        for (int source_offset = tid; source_offset < tile_count; source_offset += blockDim.x) {
            const Particle source = in[tile_base + source_offset];
            source_tile[source_offset] = {source.x, source.y, source.z, source.mass};
        }
        __syncthreads();

        if (active) {
            for (int k = 0; k < tile_count; ++k) {
                const int j = tile_base + k;
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

        __syncthreads();
        tile_base += tile_count;
    }

    if (active) {
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
