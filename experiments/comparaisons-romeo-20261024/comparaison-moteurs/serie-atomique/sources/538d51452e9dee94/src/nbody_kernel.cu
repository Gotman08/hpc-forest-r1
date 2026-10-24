// Structure "Array of Structures" (AoS): each thread owns one target particle.
struct Particle {
    float x, y, z;
    float vx, vy, vz;
    float mass;
};

// Only these source fields are needed to compute the force.
struct SourceParticle {
    float x, y, z;
    float mass;
};

// N-body step with one target per thread and CTA-level source tiling.
extern "C" __global__ void nbody_step_naive(const Particle* in, Particle* out, int n, float dt) {
    const int i = blockIdx.x * blockDim.x + threadIdx.x;
    const bool active = i < n;

    Particle target;
    if (active) {
        target = in[i];
    }

    extern __shared__ SourceParticle source_tile[];

    const float G = 1.0f;
    const float softening = 0.001f;
    float fx = 0.0f;
    float fy = 0.0f;
    float fz = 0.0f;

    for (int base = 0; base < n; base += blockDim.x) {
        const int source_index = base + threadIdx.x;
        int tile_count = n - base;
        if (tile_count > blockDim.x) {
            tile_count = blockDim.x;
        }

        if (source_index < n) {
            SourceParticle source;
            source.x = in[source_index].x;
            source.y = in[source_index].y;
            source.z = in[source_index].z;
            source.mass = in[source_index].mass;
            source_tile[threadIdx.x] = source;
        }
        __syncthreads();

        if (active) {
#pragma unroll 4
            for (int offset = 0; offset < tile_count; ++offset) {
                const int j = base + offset;
                if (i == j) continue;

                const SourceParticle source = source_tile[offset];
                const float dx = source.x - target.x;
                const float dy = source.y - target.y;
                const float dz = source.z - target.z;

                const float distSq = dx * dx + dy * dy + dz * dz + softening;
                const float inverseDistance = rsqrtf(distSq);
                const float f = (G * target.mass * source.mass) * inverseDistance * inverseDistance * inverseDistance;

                fx += f * dx;
                fy += f * dy;
                fz += f * dz;
            }
        }
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
