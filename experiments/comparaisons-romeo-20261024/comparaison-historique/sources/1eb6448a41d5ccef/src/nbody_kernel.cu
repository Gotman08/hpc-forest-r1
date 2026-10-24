struct Particle {
    float x, y, z;
    float vx, vy, vz;
    float mass;
};

extern "C" __global__ void nbody_step_naive(const Particle* in, Particle* out, int n, float dt) {
    constexpr int source_tile_size = 512;

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

    extern __shared__ float source_tile[];
    float* source_x = source_tile;
    float* source_y = source_tile + source_tile_size;
    float* source_z = source_tile + 2 * source_tile_size;
    float* source_mass = source_tile + 3 * source_tile_size;

    int base = 0;
    while (base < n) {
        int tile_count = n - base;
        if (tile_count > source_tile_size) {
            tile_count = source_tile_size;
        }

        for (int k = threadIdx.x; k < tile_count; k += blockDim.x) {
            const int source_index = base + k;
            source_x[k] = in[source_index].x;
            source_y[k] = in[source_index].y;
            source_z[k] = in[source_index].z;
            source_mass[k] = in[source_index].mass;
        }
        __syncthreads();

        if (active) {
            for (int k = 0; k < tile_count; ++k) {
                const int j = base + k;
                if (i != j) {
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
        }
        __syncthreads();
        base += tile_count;
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
