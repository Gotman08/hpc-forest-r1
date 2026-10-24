struct Particle {
    float x, y, z;
    float vx, vy, vz;
    float mass;
};

struct SourceParticle {
    float x, y, z, mass;
};

// Chaque thread conserve une cible et parcourt les sources par tuiles partagées.
extern "C" __global__ void nbody_step_naive(const Particle* in, Particle* out, int n, float dt) {
    extern __shared__ SourceParticle tile[];

    const int tid = threadIdx.x;
    const int i = blockIdx.x * blockDim.x + tid;
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

    int tile_start = 0;
    while (tile_start < n) {
        const int remaining = n - tile_start;
        const int tile_count = remaining < blockDim.x ? remaining : blockDim.x;
        const int source_index = tile_start + tid;

        if (tid < tile_count) {
            const Particle source = in[source_index];
            tile[tid].x = source.x;
            tile[tid].y = source.y;
            tile[tid].z = source.z;
            tile[tid].mass = source.mass;
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

        if (remaining <= blockDim.x) break;
        tile_start += blockDim.x;
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
