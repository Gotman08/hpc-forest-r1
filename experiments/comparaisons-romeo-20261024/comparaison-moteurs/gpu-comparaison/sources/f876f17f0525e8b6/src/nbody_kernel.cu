// Structure "Array of Structures" (AoS) : intuitive mais naïve sur GPU
// car elle empêche la coalescence parfaite des accès mémoire.
struct Particle {
    float x, y, z;
    float vx, vy, vz;
    float mass;
};

// Kernel CUDA avec tuilage des sources en mémoire partagée.
extern "C" __global__ void nbody_step_naive(const Particle* in, Particle* out, int n, float dt) {
    int i = blockIdx.x * blockDim.x + threadIdx.x;
    bool active = i < n;

    Particle target;
    if (active) {
        target = in[i];
    }

    extern __shared__ Particle source_tile[];

    const float G = 1.0f;
    const float softening = 0.001f;
    float fx = 0.0f;
    float fy = 0.0f;
    float fz = 0.0f;

    for (int tile_start = 0; tile_start < n; tile_start += blockDim.x) {
        int source_index = tile_start + threadIdx.x;
        if (source_index < n) {
            source_tile[threadIdx.x] = in[source_index];
        }
        __syncthreads();

        int remaining = n - tile_start;
        int tile_count = remaining < blockDim.x ? remaining : blockDim.x;

        if (active) {
            for (int k = 0; k < tile_count; ++k) {
                int j = tile_start + k;
                if (i == j) continue;

                Particle source = source_tile[k];
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

    if (!active) return;

    Particle p = target;
    p.vx += (fx / p.mass) * dt;
    p.vy += (fy / p.mass) * dt;
    p.vz += (fz / p.mass) * dt;

    p.x += p.vx * dt;
    p.y += p.vy * dt;
    p.z += p.vz * dt;

    out[i] = p;
}
