struct Particle {
    float x, y, z;
    float vx, vy, vz;
    float mass;
};

struct SharedSource {
    float x, y, z, mass;
};

extern "C" __global__ void nbody_step_naive(const Particle* in, Particle* out, int n, float dt) {
    extern __shared__ SharedSource source_tile[];

    const int i = blockIdx.x * blockDim.x + threadIdx.x;
    const bool active = i < n;

    Particle p;
    if (active) {
        p = in[i];
    }

    const float G = 1.0f;
    const float softening = 0.001f;
    float fx = 0.0f;
    float fy = 0.0f;
    float fz = 0.0f;

    for (int base = 0; base < n; base += blockDim.x) {
        const int source_index = base + threadIdx.x;
        if (source_index < n) {
            const Particle source = in[source_index];
            source_tile[threadIdx.x] = {source.x, source.y, source.z, source.mass};
        }

        __syncthreads();

        int tile_count = n - base;
        if (tile_count > blockDim.x) {
            tile_count = blockDim.x;
        }

        if (active) {
            for (int k = 0; k < tile_count; ++k) {
                const int j = base + k;
                if (i == j) {
                    continue;
                }

                const SharedSource source = source_tile[k];
                const float dx = source.x - p.x;
                const float dy = source.y - p.y;
                const float dz = source.z - p.z;

                const float distSq = dx * dx + dy * dy + dz * dz + softening;
                const float dist = sqrtf(distSq);
                const float f = (G * p.mass * source.mass) / (distSq * dist);

                fx += f * dx;
                fy += f * dy;
                fz += f * dz;
            }
        }

        __syncthreads();
    }

    if (active) {
        p.vx += (fx / p.mass) * dt;
        p.vy += (fy / p.mass) * dt;
        p.vz += (fz / p.mass) * dt;

        p.x += p.vx * dt;
        p.y += p.vy * dt;
        p.z += p.vz * dt;

        out[i] = p;
    }
}
