struct Particle {
    float x, y, z;
    float vx, vy, vz;
    float mass;
};

#define SOURCE_TILE_SIZE 512

extern "C" __global__ void nbody_step_naive(const Particle* in, Particle* out, int n, float dt) {
    extern __shared__ Particle source_tile[];

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

    int base = 0;
    while (base < n) {
        int panel_count = n - base;
        if (panel_count > SOURCE_TILE_SIZE) {
            panel_count = SOURCE_TILE_SIZE;
        }

        for (int t = (int)threadIdx.x; t < panel_count; t += (int)blockDim.x) {
            source_tile[t] = in[base + t];
        }
        __syncthreads();

        if (active) {
            for (int t = 0; t < panel_count; ++t) {
                const int j = base + t;
                if (i == j) continue;

                const Particle source = source_tile[t];
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
        base += panel_count;
    }

    if (!active) return;

    p.vx += (fx / p.mass) * dt;
    p.vy += (fy / p.mass) * dt;
    p.vz += (fz / p.mass) * dt;

    p.x += p.vx * dt;
    p.y += p.vy * dt;
    p.z += p.vz * dt;

    out[i] = p;
}
