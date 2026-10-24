struct SharedSourceParticle {
    float x;
    float y;
    float z;
    float mass;
};

extern "C" __global__ void nbody_step_naive(const Particle* in, Particle* out, int n, float dt) {
    const int tile_size = 1024;
    const int i = blockIdx.x * blockDim.x + threadIdx.x;
    const bool active = i < n;

    const float G = 1.0f;
    const float softening = 0.001f;

    float target_x = 0.0f;
    float target_y = 0.0f;
    float target_z = 0.0f;
    float target_mass = 0.0f;
    if (active) {
        target_x = in[i].x;
        target_y = in[i].y;
        target_z = in[i].z;
        target_mass = in[i].mass;
    }

    float fx = 0.0f;
    float fy = 0.0f;
    float fz = 0.0f;

    extern __shared__ SharedSourceParticle source_tile[];

    for (int source_base = 0; source_base < n; source_base += tile_size) {
        for (int k = threadIdx.x; k < tile_size; k += blockDim.x) {
            const int j = source_base + k;
            if (j < n) {
                source_tile[k].x = in[j].x;
                source_tile[k].y = in[j].y;
                source_tile[k].z = in[j].z;
                source_tile[k].mass = in[j].mass;
            } else {
                source_tile[k].x = 0.0f;
                source_tile[k].y = 0.0f;
                source_tile[k].z = 0.0f;
                source_tile[k].mass = 0.0f;
            }
        }

        __syncthreads();

        int tile_count = n - source_base;
        if (tile_count > tile_size) {
            tile_count = tile_size;
        }

        if (active) {
            for (int k = 0; k < tile_count; ++k) {
                const int j = source_base + k;
                if (i == j) continue;

                const float dx = source_tile[k].x - target_x;
                const float dy = source_tile[k].y - target_y;
                const float dz = source_tile[k].z - target_z;

                const float distSq = dx * dx + dy * dy + dz * dz + softening;
                const float dist = sqrtf(distSq);
                const float f = (G * target_mass * source_tile[k].mass) / (distSq * dist);

                fx += f * dx;
                fy += f * dy;
                fz += f * dz;
            }
        }

        __syncthreads();
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
