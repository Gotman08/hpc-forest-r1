// Structure Array of Structures: each particle occupies 28 bytes.
struct Particle {
    float x, y, z;
    float vx, vy, vz;
    float mass;
};

// CUDA N-body step using one cooperatively staged source tile per block.
extern "C" __global__ void nbody_step_naive(const Particle* in, Particle* out, int n, float dt) {
    extern __shared__ Particle source_tile[];

    const int source_tile_size = 1728;
    const int lane = threadIdx.x;
    const int i = blockIdx.x * blockDim.x + lane;
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

    for (int base = 0; base < n; base += source_tile_size) {
        for (int k = lane; k < source_tile_size; k += blockDim.x) {
            const int source_index = base + k;
            if (source_index < n) {
                source_tile[k] = in[source_index];
            }
        }

        // All threads, including inactive tail threads, must reach both barriers.
        __syncthreads();

        const int remaining = n - base;
        const int tile_count = remaining < source_tile_size ? remaining : source_tile_size;

        if (active) {
            for (int k = 0; k < tile_count; ++k) {
                const int j = base + k;
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

        // Ensure all readers finish before the next tile overwrites shared memory.
        __syncthreads();
    }

    if (active) {
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
