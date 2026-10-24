struct Particle {
    float x, y, z;
    float vx, vy, vz;
    float mass;
};

extern "C" __global__ void nbody_step_naive(const Particle* in, Particle* out, int n, float dt) {
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

    extern __shared__ float source_data[];
    float* source_x = source_data;
    float* source_y = source_x + blockDim.x;
    float* source_z = source_y + blockDim.x;
    float* source_mass = source_z + blockDim.x;

    int tile_start = 0;
    while (tile_start < n) {
        int tile_count = n - tile_start;
        if (tile_count > blockDim.x) {
            tile_count = blockDim.x;
        }

        if (threadIdx.x < tile_count) {
            const int source_index = tile_start + threadIdx.x;
            const Particle source = in[source_index];
            source_x[threadIdx.x] = source.x;
            source_y[threadIdx.x] = source.y;
            source_z[threadIdx.x] = source.z;
            source_mass[threadIdx.x] = source.mass;
        }
        __syncthreads();

        if (active) {
            for (int k = 0; k < tile_count; ++k) {
                const int j = tile_start + k;
                if (i == j) continue;

                float dx = source_x[k] - p.x;
                float dy = source_y[k] - p.y;
                float dz = source_z[k] - p.z;

                float distSq = dx * dx + dy * dy + dz * dz + softening;
                float dist = sqrtf(distSq);
                float f = (G * p.mass * source_mass[k]) / (distSq * dist);

                fx += f * dx;
                fy += f * dy;
                fz += f * dz;
            }
        }
        __syncthreads();

        if (tile_count == n - tile_start) {
            break;
        }
        tile_start += tile_count;
    }

    if (active) {
        p.vx += (fx / p.mass) * dt;
        p.vy += (fy / p.mass) * dt;
        p.vz += (fz / p.mass) * dt;

        p.x += p.vx * dt;
        p.y += p.vy * dt;
        p.z += p.vz * dt;

        out[i] = p;
    }
}
