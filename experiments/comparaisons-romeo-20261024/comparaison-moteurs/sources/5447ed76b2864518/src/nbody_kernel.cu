// Structure "Array of Structures" (AoS) : intuitive mais naïve sur GPU
// car elle empêche la coalescence parfaite des accès mémoire.
struct Particle {
    float x, y, z;
    float vx, vy, vz;
    float mass;
};

// Each block cooperatively loads source particles once per tile and reuses
// them across the block's target rows.
extern "C" __global__ void nbody_step_naive(const Particle* in, Particle* out, int n, float dt) {
    const int i = blockIdx.x * blockDim.x + threadIdx.x;

    const float G = 1.0f;
    const float softening = 0.001f;
    __shared__ Particle source_tile[256];

    // Do not return early: every thread must reach both barriers for each tile.
    Particle target;
    if (i < n) target = in[i];

    float fx = 0.0f;
    float fy = 0.0f;
    float fz = 0.0f;

    for (int tile_start = 0; tile_start < n; tile_start += 256) {
        const int source_index = tile_start + threadIdx.x;
        if (source_index < n) source_tile[threadIdx.x] = in[source_index];
        __syncthreads();

        if (i < n) {
            int tile_count = n - tile_start;
            if (tile_count > 256) tile_count = 256;

            for (int k = 0; k < tile_count; ++k) {
                const int j = tile_start + k;
                if (i == j) continue;

                const Particle source = source_tile[k];
                float dx = source.x - target.x;
                float dy = source.y - target.y;
                float dz = source.z - target.z;

                float distSq = dx * dx + dy * dy + dz * dz + softening;
                float dist = sqrtf(distSq);

                float f = (G * target.mass * source.mass) / (distSq * dist);

                fx += f * dx;
                fy += f * dy;
                fz += f * dz;
            }
        }
        __syncthreads();
    }

    if (i < n) {
        Particle p = target;
        p.vx += (fx / p.mass) * dt;
        p.vy += (fy / p.mass) * dt;
        p.vz += (fz / p.mass) * dt;

        p.x += p.vx * dt;
        p.y += p.vy * dt;
        p.z += p.vz * dt;

        out[i] = p;
    }
}
