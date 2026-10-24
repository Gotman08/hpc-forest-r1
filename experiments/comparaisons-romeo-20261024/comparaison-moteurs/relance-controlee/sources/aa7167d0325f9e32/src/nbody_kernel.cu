struct Particle {
    float x, y, z;
    float vx, vy, vz;
    float mass;
};

enum { kSourceTileSize = 512 };

extern "C" __global__ void nbody_step_naive(const Particle* in, Particle* out, int n, float dt) {
    const int i = blockIdx.x * blockDim.x + threadIdx.x;
    const bool active = i < n;

    __shared__ float tile_x[kSourceTileSize];
    __shared__ float tile_y[kSourceTileSize];
    __shared__ float tile_z[kSourceTileSize];
    __shared__ float tile_mass[kSourceTileSize];

    const float G = 1.0f;
    const float softening = 0.001f;

    float fx = 0.0f;
    float fy = 0.0f;
    float fz = 0.0f;

    for (int tile_start = 0; tile_start < n;) {
        int tile_count = n - tile_start;
        if (tile_count > kSourceTileSize) {
            tile_count = kSourceTileSize;
        }

        for (int k = threadIdx.x; k < tile_count; k += blockDim.x) {
            const int source_index = tile_start + k;
            tile_x[k] = in[source_index].x;
            tile_y[k] = in[source_index].y;
            tile_z[k] = in[source_index].z;
            tile_mass[k] = in[source_index].mass;
        }
        __syncthreads();

        if (active) {
            for (int k = 0; k < tile_count; ++k) {
                const int j = tile_start + k;
                if (i == j) {
                    continue;
                }

                const float dx = tile_x[k] - in[i].x;
                const float dy = tile_y[k] - in[i].y;
                const float dz = tile_z[k] - in[i].z;

                const float distSq = dx * dx + dy * dy + dz * dz + softening;
                const float dist = sqrtf(distSq);
                const float f = (G * in[i].mass * tile_mass[k]) / (distSq * dist);

                fx += f * dx;
                fy += f * dy;
                fz += f * dz;
            }
        }

        __syncthreads();
        tile_start += tile_count;
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
