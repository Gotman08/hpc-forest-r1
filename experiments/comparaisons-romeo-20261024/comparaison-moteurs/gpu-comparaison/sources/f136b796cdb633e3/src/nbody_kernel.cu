struct Particle {
    float x, y, z;
    float vx, vy, vz;
    float mass;
};

extern "C" __global__ void nbody_step_naive(const Particle* in, Particle* out, int n, float dt) {
    const int i = blockIdx.x * blockDim.x + threadIdx.x;
    const bool active = i < n;

    Particle target;
    if (active) {
        target = in[i];
    }

    const float G = 1.0f;
    const float softening = 0.001f;

    extern __shared__ float shared_source[];
    float* source_x = shared_source;
    float* source_y = source_x + blockDim.x;
    float* source_z = source_y + blockDim.x;
    float* source_mass = source_z + blockDim.x;

    float fx = 0.0f;
    float fy = 0.0f;
    float fz = 0.0f;

    for (int tile_base = 0; tile_base < n; tile_base += blockDim.x) {
        const int source_index = tile_base + threadIdx.x;
        if (source_index < n) {
            source_x[threadIdx.x] = in[source_index].x;
            source_y[threadIdx.x] = in[source_index].y;
            source_z[threadIdx.x] = in[source_index].z;
            source_mass[threadIdx.x] = in[source_index].mass;
        }

        __syncthreads();

        int tile_count = n - tile_base;
        if (tile_count > blockDim.x) {
            tile_count = blockDim.x;
        }

        if (active) {
            for (int k = 0; k < tile_count; ++k) {
                if (i == tile_base + k) continue;

                const float dx = source_x[k] - target.x;
                const float dy = source_y[k] - target.y;
                const float dz = source_z[k] - target.z;

                const float distSq = dx * dx + dy * dy + dz * dz + softening;
                const float dist = sqrtf(distSq);
                const float f = (G * target.mass * source_mass[k]) / (distSq * dist);

                fx += f * dx;
                fy += f * dy;
                fz += f * dz;
            }
        }

        __syncthreads();
    }

    if (active) {
        target.vx += (fx / target.mass) * dt;
        target.vy += (fy / target.mass) * dt;
        target.vz += (fz / target.mass) * dt;

        target.x += target.vx * dt;
        target.y += target.vy * dt;
        target.z += target.vz * dt;

        out[i] = target;
    }
}
