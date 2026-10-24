struct Particle {
    float x, y, z;
    float vx, vy, vz;
    float mass;
};

extern "C" __global__ void nbody_step_naive(const Particle* in, Particle* out, int n, float dt) {
    const int lane = threadIdx.x & 31;
    const int warp = threadIdx.x >> 5;
    const int warps_per_block = blockDim.x >> 5;
    const int i = blockIdx.x * warps_per_block + warp;
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

    // All CTA threads stage each panel, including threads in inactive output warps.
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
            for (int k = lane; k < panel_count; k += 32) {
                const int j = panel_start + k;
                if (j == i) continue;

                const Particle source = source_panel[k];
                const float dx = source.x - target.x;
                const float dy = source.y - target.y;
                const float dz = source.z - target.z;
                const float distSq = dx * dx + dy * dy + dz * dz + softening;
                const float dist = sqrtf(distSq);
                const float f = (G * target.mass * source.mass) / (distSq * dist);

                fx += f * dx;
                fy += f * dy;
                fz += f * dz;
            }
        }

        // Every thread must finish reading before the shared panel is overwritten.
        __syncthreads();
        panel_start += panel_count;
    }

    for (int offset = 16; offset > 0; offset >>= 1) {
        fx += __shfl_down_sync(0xffffffffu, fx, offset);
        fy += __shfl_down_sync(0xffffffffu, fy, offset);
        fz += __shfl_down_sync(0xffffffffu, fz, offset);
    }

    if (lane == 0 && active) {
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
