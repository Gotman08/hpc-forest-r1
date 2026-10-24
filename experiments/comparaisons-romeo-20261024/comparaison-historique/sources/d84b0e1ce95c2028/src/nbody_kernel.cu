struct Particle {
    float x, y, z;
    float vx, vy, vz;
    float mass;
};

constexpr int SOURCE_TILE_SIZE = 896;

extern "C" __global__ void nbody_step_naive(const Particle* in, Particle* out, int n, float dt) {
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

    extern __shared__ Particle shared_sources[];

    for (int tile_base = 0; tile_base < n;) {
        int tile_count = n - tile_base;
        if (tile_count > SOURCE_TILE_SIZE) {
            tile_count = SOURCE_TILE_SIZE;
        }

        for (int k = threadIdx.x; k < tile_count; k += blockDim.x) {
            shared_sources[k] = in[tile_base + k];
        }
        __syncthreads();

        if (active) {
            for (int k = 0; k < tile_count; ++k) {
                const int j = tile_base + k;
                if (i == j) continue;

                const Particle source = shared_sources[k];
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
