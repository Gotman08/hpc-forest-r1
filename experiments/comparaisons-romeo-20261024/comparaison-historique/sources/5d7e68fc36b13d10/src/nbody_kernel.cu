struct Particle {
    float x, y, z;
    float vx, vy, vz;
    float mass;
};

extern "C" __global__ void nbody_step_naive(const Particle* in, Particle* out, int n, float dt) {
    const int tid = threadIdx.x;
    const int i = blockIdx.x * blockDim.x + tid;
    const bool target_valid = i < n;

    Particle target;
    if (target_valid) {
        target = in[i];
    }

    extern __shared__ float shared[];
    float* source_x = shared;
    float* source_y = source_x + blockDim.x;
    float* source_z = source_y + blockDim.x;
    float* source_mass = source_z + blockDim.x;

    const float G = 1.0f;
    const float softening = 0.001f;
    float fx = 0.0f;
    float fy = 0.0f;
    float fz = 0.0f;

    for (int base = 0; base < n; base += blockDim.x) {
        const int source_index = base + tid;
        if (source_index < n) {
            source_x[tid] = in[source_index].x;
            source_y[tid] = in[source_index].y;
            source_z[tid] = in[source_index].z;
            source_mass[tid] = in[source_index].mass;
        }

        __syncthreads();

        if (target_valid) {
            int tile_count = n - base;
            if (tile_count > blockDim.x) {
                tile_count = blockDim.x;
            }

            for (int k = 0; k < tile_count; ++k) {
                const int j = base + k;
                if (i == j) continue;

                const float dx = source_x[k] - target.x;
                const float dy = source_y[k] - target.y;
                const float dz = source_z[k] - target.z;
                const float distSq = dx * dx + dy * dy + dz * dz + softening;

                const float initialInvDist = rsqrtf(distSq);
                const float initialInvDistSq = initialInvDist * initialInvDist;
                const float invDist = initialInvDist *
                    (1.5f - (0.5f * distSq) * initialInvDistSq);
                const float invDist3 = invDist * invDist * invDist;
                const float f = (G * target.mass * source_mass[k]) * invDist3;

                fx += f * dx;
                fy += f * dy;
                fz += f * dz;
            }
        }

        __syncthreads();
    }

    if (target_valid) {
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
