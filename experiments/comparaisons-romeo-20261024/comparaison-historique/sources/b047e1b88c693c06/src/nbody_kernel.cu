struct Particle {
    float x, y, z;
    float vx, vy, vz;
    float mass;
};

extern "C" __global__ void nbody_step_naive(const Particle* in, Particle* out, int n, float dt) {
    extern __shared__ Particle source_tile[];

    const unsigned int i = blockIdx.x * blockDim.x + threadIdx.x;
    const bool active = i < static_cast<unsigned int>(n);

    const float G = 1.0f;
    const float softening = 0.001f;
    const int source_tile_width = 512;

    float fx = 0.0f;
    float fy = 0.0f;
    float fz = 0.0f;

    int base = 0;
    const int block_width = static_cast<int>(blockDim.x);
    while (base < n) {
        const int remaining = n - base;
        const int tile_count = remaining < source_tile_width ? remaining : source_tile_width;

        for (int k = static_cast<int>(threadIdx.x); k < tile_count; k += block_width) {
            source_tile[k] = in[base + k];
        }
        __syncthreads();

        if (active) {
            for (int k = 0; k < tile_count; ++k) {
                const int j = base + k;
                if (i == static_cast<unsigned int>(j)) continue;

                const Particle source = source_tile[k];
                float dx = source.x - in[i].x;
                float dy = source.y - in[i].y;
                float dz = source.z - in[i].z;

                float distSq = dx * dx + dy * dy + dz * dz + softening;
                float dist = sqrtf(distSq);

                float f = (G * in[i].mass * source.mass) / (distSq * dist);

                fx += f * dx;
                fy += f * dy;
                fz += f * dz;
            }
        }

        __syncthreads();
        base += tile_count;
    }

    if (active) {
        Particle p = in[i];
        p.vx += (fx / p.mass) * dt;
        p.vy += (fy / p.mass) * dt;
        p.vz += (fz / p.mass) * dt;

        p.x += p.vx * dt;
        p.y += p.vy * dt;
        p.z += p.vz * dt;

        out[i] = p;
    }
}
