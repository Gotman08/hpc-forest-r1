struct Particle {
    float x, y, z;
    float vx, vy, vz;
    float mass;
};

extern "C" __global__ void nbody_step_naive(const Particle* in, Particle* out, int n, float dt) {
    const int lane = threadIdx.x;
    const int i = blockIdx.x * blockDim.x + lane;
    const bool active = i < n;

    extern __shared__ Particle source_tile[];

    const float G = 1.0f;
    const float softening = 0.001f;
    float fx = 0.0f;
    float fy = 0.0f;
    float fz = 0.0f;

    for (int tile_base = 0; tile_base < n; tile_base += blockDim.x) {
        const int j = tile_base + lane;
        if (j < n) {
            source_tile[lane] = in[j];
        }
        __syncthreads();

        int tile_count = n - tile_base;
        if (tile_count > blockDim.x) {
            tile_count = blockDim.x;
        }

        if (active) {
            for (int k = 0; k < tile_count; ++k) {
                const int source_index = tile_base + k;
                if (i == source_index) continue;

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
    }

    if (!active) return;

    Particle p = in[i];
    p.vx += (fx / p.mass) * dt;
    p.vy += (fy / p.mass) * dt;
    p.vz += (fz / p.mass) * dt;

    p.x += p.vx * dt;
    p.y += p.vy * dt;
    p.z += p.vz * dt;

    out[i] = p;
}
