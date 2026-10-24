struct Particle {
    float x, y, z;
    float vx, vy, vz;
    float mass;
};

extern "C" __global__ void nbody_step_naive(const Particle* in, Particle* out, int n, float dt) {
    const int tid = threadIdx.x;
    const int target_base = blockIdx.x * (2 * blockDim.x);
    const int i0 = target_base + 2 * tid;
    const int i1 = i0 + 1;
    const bool valid0 = i0 < n;
    const bool valid1 = i1 < n;

    Particle target0;
    Particle target1;
    if (valid0) {
        target0 = in[i0];
    }
    if (valid1) {
        target1 = in[i1];
    }

    extern __shared__ float shared[];
    float* source_x = shared;
    float* source_y = source_x + blockDim.x;
    float* source_z = source_y + blockDim.x;
    float* source_mass = source_z + blockDim.x;

    const float G = 1.0f;
    const float softening = 0.001f;
    float fx0 = 0.0f;
    float fy0 = 0.0f;
    float fz0 = 0.0f;
    float fx1 = 0.0f;
    float fy1 = 0.0f;
    float fz1 = 0.0f;

    for (int base = 0; base < n; base += blockDim.x) {
        const int source_index = base + tid;
        if (source_index < n) {
            source_x[tid] = in[source_index].x;
            source_y[tid] = in[source_index].y;
            source_z[tid] = in[source_index].z;
            source_mass[tid] = in[source_index].mass;
        }

        __syncthreads();

        int tile_count = n - base;
        if (tile_count > blockDim.x) {
            tile_count = blockDim.x;
        }

        for (int k = 0; k < tile_count; ++k) {
            const int j = base + k;
            const float sx = source_x[k];
            const float sy = source_y[k];
            const float sz = source_z[k];
            const float sm = source_mass[k];

            if (valid0 && i0 != j) {
                const float dx = sx - target0.x;
                const float dy = sy - target0.y;
                const float dz = sz - target0.z;
                const float distSq = dx * dx + dy * dy + dz * dz + softening;
                const float dist = sqrtf(distSq);
                const float f = (G * target0.mass * sm) / (distSq * dist);
                fx0 += f * dx;
                fy0 += f * dy;
                fz0 += f * dz;
            }

            if (valid1 && i1 != j) {
                const float dx = sx - target1.x;
                const float dy = sy - target1.y;
                const float dz = sz - target1.z;
                const float distSq = dx * dx + dy * dy + dz * dz + softening;
                const float dist = sqrtf(distSq);
                const float f = (G * target1.mass * sm) / (distSq * dist);
                fx1 += f * dx;
                fy1 += f * dy;
                fz1 += f * dz;
            }
        }

        __syncthreads();
    }

    if (valid0) {
        Particle p = target0;
        p.vx += (fx0 / p.mass) * dt;
        p.vy += (fy0 / p.mass) * dt;
        p.vz += (fz0 / p.mass) * dt;
        p.x += p.vx * dt;
        p.y += p.vy * dt;
        p.z += p.vz * dt;
        out[i0] = p;
    }

    if (valid1) {
        Particle p = target1;
        p.vx += (fx1 / p.mass) * dt;
        p.vy += (fy1 / p.mass) * dt;
        p.vz += (fz1 / p.mass) * dt;
        p.x += p.vx * dt;
        p.y += p.vy * dt;
        p.z += p.vz * dt;
        out[i1] = p;
    }
}
