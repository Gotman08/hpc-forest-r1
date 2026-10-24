// Structure "Array of Structures" (AoS).
struct Particle {
    float x, y, z;
    float vx, vy, vz;
    float mass;
};

// Tiled variant: keep one target particle per thread and stage source
// particles in shared memory for reuse by the block's targets.
extern "C" __global__ void nbody_step_naive(const Particle* in, Particle* out, int n, float dt) {
    const int i = blockIdx.x * blockDim.x + threadIdx.x;

    // The launch configuration uses 256 threads. This is 256 * 7 floats
    // (7168 bytes), below the 49152-byte shared-memory limit.
    __shared__ Particle source_tile[256];

    const float G = 1.0f;
    const float softening = 0.001f;
    float fx = 0.0f;
    float fy = 0.0f;
    float fz = 0.0f;

    int tile_start = 0;
    while (tile_start < n) {
        const int remaining = n - tile_start;
        const int tile_count = remaining < blockDim.x ? remaining : blockDim.x;

        if (threadIdx.x < tile_count) {
            source_tile[threadIdx.x] = in[tile_start + threadIdx.x];
        }
        // All threads, including those outside the target tail, must reach
        // each block-wide barrier.
        __syncthreads();

        if (i < n) {
            for (int offset = 0; offset < tile_count; ++offset) {
                const int j = tile_start + offset;
                if (i == j) continue;

                float dx = source_tile[offset].x - in[i].x;
                float dy = source_tile[offset].y - in[i].y;
                float dz = source_tile[offset].z - in[i].z;

                float distSq = dx * dx + dy * dy + dz * dz + softening;
                float dist = sqrtf(distSq);

                float f = (G * in[i].mass * source_tile[offset].mass) / (distSq * dist);

                fx += f * dx;
                fy += f * dy;
                fz += f * dz;
            }
        }

        // Synchronize before overwriting a tile, but no extra barrier is
        // needed once the final tile has been consumed.
        if (remaining > blockDim.x) {
            __syncthreads();
        }
        tile_start += tile_count;
    }

    if (i >= n) return;

    // Explicit Euler integration, with the baseline arithmetic unchanged.
    Particle p = in[i];
    p.vx += (fx / p.mass) * dt;
    p.vy += (fy / p.mass) * dt;
    p.vz += (fz / p.mass) * dt;

    p.x += p.vx * dt;
    p.y += p.vy * dt;
    p.z += p.vz * dt;

    out[i] = p;
}
