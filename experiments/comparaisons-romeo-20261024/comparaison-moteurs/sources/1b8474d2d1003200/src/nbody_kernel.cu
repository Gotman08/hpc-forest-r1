// Structure "Array of Structures" (AoS) : intuitive mais naïve sur GPU
// car elle empêche la coalescence parfaite des accès mémoire.
struct Particle {
    float x, y, z;
    float vx, vy, vz;
    float mass;
};

// Each target thread reuses a block-sized shared-memory tile of source data.
extern "C" __global__ void nbody_step_naive(const Particle* in, Particle* out, int n, float dt) {
    const int i = blockIdx.x * blockDim.x + threadIdx.x;
    const bool active = i < n;

    // Keep one target per thread; inactive tail threads still participate in barriers.
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
    const int tile_width = blockDim.x;
    float* source_x = source_tile;
    float* source_y = source_x + tile_width;
    float* source_z = source_y + tile_width;
    float* source_mass = source_z + tile_width;

    int tile_start = 0;
    while (tile_start < n) {
        const int remaining = n - tile_start;
        const int tile_count = remaining < tile_width ? remaining : tile_width;
        const int source_index = tile_start + threadIdx.x;

        if (source_index < n) {
            source_x[threadIdx.x] = in[source_index].x;
            source_y[threadIdx.x] = in[source_index].y;
            source_z[threadIdx.x] = in[source_index].z;
            source_mass[threadIdx.x] = in[source_index].mass;
        }
        __syncthreads();

        // Visit sources in ascending index order and preserve the baseline arithmetic.
        for (int k = 0; k < tile_count; ++k) {
            const int j = tile_start + k;
            if (active && i != j) {
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
        tile_start += tile_count;
    }

    if (!active) {
        return;
    }

    // Intégration d'Euler explicite
    Particle p = target;
    p.vx += (fx / p.mass) * dt;
    p.vy += (fy / p.mass) * dt;
    p.vz += (fz / p.mass) * dt;

    p.x += p.vx * dt;
    p.y += p.vy * dt;
    p.z += p.vz * dt;

    out[i] = p;
}
