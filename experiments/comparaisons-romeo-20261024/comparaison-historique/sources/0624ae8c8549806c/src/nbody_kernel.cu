// Structure "Array of Structures" (AoS) : intuitive mais naïve sur GPU
// car elle empêche la coalescence parfaite des accès mémoire.
struct Particle {
    float x, y, z;
    float vx, vy, vz;
    float mass;
};

// Source tiles are larger than the target block; each thread stages multiple
// records and reuses the tile across the active target threads.
constexpr int kSourceTileSize = 1024;

extern "C" __global__ void nbody_step_naive(const Particle* in, Particle* out, int n, float dt) {
    extern __shared__ Particle source_tile[];

    const int thread_id = threadIdx.x;
    const int i = blockIdx.x * blockDim.x + thread_id;
    Particle target;
    if (i < n) {
        target = in[i];
    }

    const float G = 1.0f;
    const float softening = 0.001f;

    float fx = 0.0f;
    float fy = 0.0f;
    float fz = 0.0f;

    // All threads, including target-tail threads, participate in both barriers.
    for (int tile_start = 0; tile_start < n;) {
        const int remaining = n - tile_start;
        const int tile_count = remaining < kSourceTileSize ? remaining : kSourceTileSize;

        // The 128-thread block cooperatively loads up to 1024 source records.
        for (int offset = thread_id; offset < tile_count; offset += blockDim.x) {
            source_tile[offset] = in[tile_start + offset];
        }
        __syncthreads();

        if (i < n) {
            for (int offset = 0; offset < tile_count; ++offset) {
                const int j = tile_start + offset;
                if (i == j) continue;

                const Particle source = source_tile[offset];
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
        __syncthreads();
        tile_start += tile_count;
    }

    if (i < n) {
        target.vx += (fx / target.mass) * dt;
        target.vy += (fy / target.mass) * dt;
        target.vz += (fz / target.mass) * dt;

        target.x += target.vx * dt;
        target.y += target.vy * dt;
        target.z += target.vz * dt;

        out[i] = target;
    }
}
