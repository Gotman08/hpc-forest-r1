struct Particle {
    float x, y, z;
    float vx, vy, vz;
    float mass;
};

extern "C" __global__ void nbody_step_naive(const Particle* in, Particle* out, int n, float dt) {
    constexpr int SOURCE_TILE_SIZE = 1536;
    extern __shared__ Particle source_tile[];

    const int i = blockIdx.x * blockDim.x + threadIdx.x;
    const int tid = threadIdx.x;
    const float G = 1.0f;
    const float softening = 0.001f;

    Particle p;
    if (i < n) {
        p = in[i];
    }

    float fx = 0.0f;
    float fy = 0.0f;
    float fz = 0.0f;

    for (int tile_start = 0; tile_start < n; ) {
        const int remaining = n - tile_start;
        const int tile_count = remaining < SOURCE_TILE_SIZE ? remaining : SOURCE_TILE_SIZE;

        for (int k = tid; k < tile_count; k += blockDim.x) {
            source_tile[k] = in[tile_start + k];
        }
        __syncthreads();

        if (i < n) {
            for (int k = 0; k < tile_count; ++k) {
                const int j = tile_start + k;
                if (i == j) continue;

                const Particle source = source_tile[k];
                float dx = source.x - p.x;
                float dy = source.y - p.y;
                float dz = source.z - p.z;

                float distSq = dx * dx + dy * dy + dz * dz + softening;
                float dist = sqrtf(distSq);

                float f = (G * p.mass * source.mass) / (distSq * dist);

                fx += f * dx;
                fy += f * dy;
                fz += f * dz;
            }
        }

        __syncthreads();
        tile_start += tile_count;
    }

    if (i < n) {
        p.vx += (fx / p.mass) * dt;
        p.vy += (fy / p.mass) * dt;
        p.vz += (fz / p.mass) * dt;

        p.x += p.vx * dt;
        p.y += p.vy * dt;
        p.z += p.vz * dt;

        out[i] = p;
    }
}
