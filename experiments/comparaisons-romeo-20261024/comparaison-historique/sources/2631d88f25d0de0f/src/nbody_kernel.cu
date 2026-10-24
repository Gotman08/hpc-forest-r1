// Structure "Array of Structures" (AoS).
struct Particle {
    float x, y, z;
    float vx, vy, vz;
    float mass;
};

extern "C" __global__ void nbody_step_naive(const Particle* in, Particle* out, int n, float dt) {
    const int i = blockIdx.x * blockDim.x + threadIdx.x;
    const bool active = i < n;

    constexpr int tile_capacity = 1024;
    extern __shared__ Particle source_panel[];

    Particle target;
    if (active) {
        target = in[i];
    }

    const float G = 1.0f;
    const float softening = 0.001f;
    float fx = 0.0f;
    float fy = 0.0f;
    float fz = 0.0f;

    // All threads stage each bounded panel, including threads without an output.
    int panel_start = 0;
    while (panel_start < n) {
        int panel_count = n - panel_start;
        if (panel_count > tile_capacity) {
            panel_count = tile_capacity;
        }

        for (int k = static_cast<int>(threadIdx.x); k < panel_count;
             k += static_cast<int>(blockDim.x)) {
            source_panel[k] = in[panel_start + k];
        }
        __syncthreads();

        if (active) {
            for (int k = 0; k < panel_count; ++k) {
                const int j = panel_start + k;
                if (i == j) continue;

                const Particle source = source_panel[k];
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

        // Ensure all readers finish before this panel storage is overwritten.
        __syncthreads();
        panel_start += panel_count;
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
