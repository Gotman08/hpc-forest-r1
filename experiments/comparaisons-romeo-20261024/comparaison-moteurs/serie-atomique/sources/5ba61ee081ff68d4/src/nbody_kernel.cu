// Structure "Array of Structures" (AoS).
struct Particle {
    float x, y, z;
    float vx, vy, vz;
    float mass;
};

// Compact shared-memory representation of a source particle.
struct SharedSource {
    float x, y, z, mass;
};

// Each CTA processes one target per thread and reuses 256-source chunks.
extern "C" __global__ void nbody_step_naive(const Particle* in, Particle* out, int n, float dt) {
    const int i = blockIdx.x * blockDim.x + threadIdx.x;
    const int lane = threadIdx.x;
    const int source_tile_size = 256;

    const float G = 1.0f;
    const float softening = 0.001f;
    float fx = 0.0f;
    float fy = 0.0f;
    float fz = 0.0f;

    extern __shared__ SharedSource source_tile[];

    for (int source_base = 0; source_base < n;) {
        const int remaining = n - source_base;
        const int tile_count = remaining < source_tile_size ? remaining : source_tile_size;

        // The 128-thread CTA cooperatively loads up to two sources per thread.
        for (int k = lane; k < tile_count; k += blockDim.x) {
            const int j = source_base + k;
            source_tile[k].x = in[j].x;
            source_tile[k].y = in[j].y;
            source_tile[k].z = in[j].z;
            source_tile[k].mass = in[j].mass;
        }
        __syncthreads();

        // Tail threads remain in the barriers but do not compute or write output.
        if (i < n) {
            for (int k = 0; k < tile_count; ++k) {
                const int j = source_base + k;
                if (i == j) continue;

                const float dx = source_tile[k].x - in[i].x;
                const float dy = source_tile[k].y - in[i].y;
                const float dz = source_tile[k].z - in[i].z;

                const float distSq = dx * dx + dy * dy + dz * dz + softening;
                const float dist = sqrtf(distSq);
                const float f = (G * in[i].mass * source_tile[k].mass) / (distSq * dist);

                fx += f * dx;
                fy += f * dy;
                fz += f * dz;
            }
        }
        __syncthreads();
        source_base += tile_count;
    }

    if (i >= n) return;

    Particle p = in[i];
    p.vx += (fx / p.mass) * dt;
    p.vy += (fy / p.mass) * dt;
    p.vz += (fz / p.mass) * dt;

    p.x += p.vx * dt;
    p.y += p.vy * dt;
    p.z += p.vz * dt;

    out[i] = p;
}
