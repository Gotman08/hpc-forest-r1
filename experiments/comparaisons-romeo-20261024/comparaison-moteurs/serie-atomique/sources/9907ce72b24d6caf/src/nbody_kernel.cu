struct Particle {
    float x, y, z;
    float vx, vy, vz;
    float mass;
};

struct SourceParticle {
    float x, y, z;
    float mass;
};

extern "C" __global__ void nbody_step_naive(const Particle* in, Particle* out, int n, float dt) {
    extern __shared__ SourceParticle source_tile[];

    const int i = blockIdx.x * blockDim.x + threadIdx.x;
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

    for (int tile_begin = 0; tile_begin < n; tile_begin += blockDim.x) {
        const int source_index = tile_begin + threadIdx.x;
        if (source_index < n) {
            const Particle source = in[source_index];
            source_tile[threadIdx.x].x = source.x;
            source_tile[threadIdx.x].y = source.y;
            source_tile[threadIdx.x].z = source.z;
            source_tile[threadIdx.x].mass = source.mass;
        }
        __syncthreads();

        int tile_size = n - tile_begin;
        if (tile_size > blockDim.x) {
            tile_size = blockDim.x;
        }

        if (active) {
            for (int k = 0; k < tile_size; ++k) {
                const int j = tile_begin + k;
                if (i == j) continue;

                const SourceParticle source = source_tile[k];
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
