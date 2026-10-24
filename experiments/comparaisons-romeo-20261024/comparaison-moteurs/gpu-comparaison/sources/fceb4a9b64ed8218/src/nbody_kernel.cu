struct Particle {
    float x, y, z;
    float vx, vy, vz;
    float mass;
};

struct SourceParticle {
    float x, y, z, mass;
};

// Une cible par thread; chaque bloc réutilise une tuile de sources en mémoire partagée.
extern "C" __global__ void nbody_step_naive(const Particle* in, Particle* out, int n, float dt) {
    extern __shared__ SourceParticle tile[];

    const int tid = threadIdx.x;
    const int i = blockIdx.x * blockDim.x + tid;
    const bool active = i < n;
    const int tile_capacity = 2 * blockDim.x;

    Particle target;
    if (active) {
        target = in[i];
    }

    const float G = 1.0f;
    const float softening = 0.001f;

    float fx = 0.0f;
    float fy = 0.0f;
    float fz = 0.0f;

    int tile_start = 0;
    while (tile_start < n) {
        const int remaining = n - tile_start;
        const int tile_count = remaining < tile_capacity ? remaining : tile_capacity;

        for (int source_offset = tid; source_offset < tile_count; source_offset += blockDim.x) {
            const Particle source = in[tile_start + source_offset];
            tile[source_offset].x = source.x;
            tile[source_offset].y = source.y;
            tile[source_offset].z = source.z;
            tile[source_offset].mass = source.mass;
        }
        __syncthreads();

        if (active) {
            for (int lane = 0; lane < tile_count; ++lane) {
                const int j = tile_start + lane;
                if (i == j) continue;

                float dx = tile[lane].x - target.x;
                float dy = tile[lane].y - target.y;
                float dz = tile[lane].z - target.z;

                float distSq = dx * dx + dy * dy + dz * dz + softening;
                float dist = sqrtf(distSq);

                float f = (G * target.mass * tile[lane].mass) / (distSq * dist);

                fx += f * dx;
                fy += f * dy;
                fz += f * dz;
            }
        }
        __syncthreads();

        if (remaining <= tile_capacity) break;
        tile_start += tile_capacity;
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
