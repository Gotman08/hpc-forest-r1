struct Particle {
    float x, y, z;
    float vx, vy, vz;
    float mass;
};

enum { kSourceTileSize = 512 };

extern "C" __global__ void nbody_step_naive(const Particle* in, Particle* out, int n, float dt) {
    const unsigned int first = blockIdx.x * (2u * blockDim.x) + threadIdx.x;
    const unsigned int limit = static_cast<unsigned int>(n);
    const unsigned int second = first + blockDim.x;
    const bool active0 = first < limit;
    const bool active1 = second < limit;

    Particle p0;
    Particle p1;
    if (active0) p0 = in[first];
    if (active1) p1 = in[second];

    __shared__ float tile_x[kSourceTileSize];
    __shared__ float tile_y[kSourceTileSize];
    __shared__ float tile_z[kSourceTileSize];
    __shared__ float tile_mass[kSourceTileSize];

    const float G = 1.0f;
    const float softening = 0.001f;

    float fx0 = 0.0f;
    float fy0 = 0.0f;
    float fz0 = 0.0f;
    float fx1 = 0.0f;
    float fy1 = 0.0f;
    float fz1 = 0.0f;

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

        if (active0) {
            for (int k = 0; k < tile_count; ++k) {
                const unsigned int source_index = static_cast<unsigned int>(tile_start + k);
                if (first != source_index) {
                    const float dx = tile_x[k] - p0.x;
                    const float dy = tile_y[k] - p0.y;
                    const float dz = tile_z[k] - p0.z;

                    const float distSq = dx * dx + dy * dy + dz * dz + softening;
                    const float dist = sqrtf(distSq);
                    const float f = (G * p0.mass * tile_mass[k]) / (distSq * dist);

                    fx0 += f * dx;
                    fy0 += f * dy;
                    fz0 += f * dz;
                }
            }
        }

        if (active1) {
            for (int k = 0; k < tile_count; ++k) {
                const unsigned int source_index = static_cast<unsigned int>(tile_start + k);
                if (second != source_index) {
                    const float dx = tile_x[k] - p1.x;
                    const float dy = tile_y[k] - p1.y;
                    const float dz = tile_z[k] - p1.z;

                    const float distSq = dx * dx + dy * dy + dz * dz + softening;
                    const float dist = sqrtf(distSq);
                    const float f = (G * p1.mass * tile_mass[k]) / (distSq * dist);

                    fx1 += f * dx;
                    fy1 += f * dy;
                    fz1 += f * dz;
                }
            }
        }

        __syncthreads();
        tile_start += tile_count;
    }

    if (active0) {
        p0.vx += (fx0 / p0.mass) * dt;
        p0.vy += (fy0 / p0.mass) * dt;
        p0.vz += (fz0 / p0.mass) * dt;

        p0.x += p0.vx * dt;
        p0.y += p0.vy * dt;
        p0.z += p0.vz * dt;

        out[first] = p0;
    }

    if (active1) {
        p1.vx += (fx1 / p1.mass) * dt;
        p1.vy += (fy1 / p1.mass) * dt;
        p1.vz += (fz1 / p1.mass) * dt;

        p1.x += p1.vx * dt;
        p1.y += p1.vy * dt;
        p1.z += p1.vz * dt;

        out[second] = p1;
    }
}
