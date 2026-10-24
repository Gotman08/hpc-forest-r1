// Structure of arrays-of-structures particle data; keep this layout unchanged.
struct Particle {
    float x, y, z;
    float vx, vy, vz;
    float mass;
};

// Each block reuses a cooperatively staged source tile across its target threads.
extern "C" __global__ void nbody_step_naive(const Particle* in, Particle* out, int n, float dt) {
    constexpr int kSourceTileSize = 1408;
    extern __shared__ Particle staged_particles[];

    const int i = blockIdx.x * blockDim.x + threadIdx.x;
    const int thread = static_cast<int>(threadIdx.x);
    const int stride = static_cast<int>(blockDim.x);
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

    for (int base = 0; base < n;) {
        const int remaining = n - base;
        const int tile_count = remaining < kSourceTileSize ? remaining : kSourceTileSize;

        for (int k = thread; k < tile_count; k += stride) {
            staged_particles[k] = in[base + k];
        }
        __syncthreads();

        if (active) {
            for (int k = 0; k < tile_count; ++k) {
                const int j = base + k;
                if (i == j) continue;

                const Particle source = staged_particles[k];
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

        // All threads, including inactive target lanes, must reach this barrier
        // before the shared tile is overwritten by the next iteration.
        __syncthreads();
        base += tile_count;
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
