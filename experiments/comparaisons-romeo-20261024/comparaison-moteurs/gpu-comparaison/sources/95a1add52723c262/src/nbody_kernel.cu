// Structure "Array of Structures" (AoS) : intuitive mais naïve sur GPU
// car elle empêche la coalescence parfaite des accès mémoire.
struct Particle {
    float x, y, z;
    float vx, vy, vz;
    float mass;
};

// Réutilise en mémoire partagée une tuile de sources pour les sorties du bloc.
extern "C" __global__ void nbody_step_naive(const Particle* in, Particle* out, int n, float dt) {
    int i = blockIdx.x * blockDim.x + threadIdx.x;
    int block_size = (int)blockDim.x;

    const float G = 1.0f;
    const float softening = 0.001f;

    Particle target;
    if (i < n) {
        target = in[i];
    }

    float fx = 0.0f;
    float fy = 0.0f;
    float fz = 0.0f;

    extern __shared__ Particle source_tile[];

    for (int tile_start = 0; tile_start < n; tile_start += block_size) {
        int source_index = tile_start + (int)threadIdx.x;
        if (source_index < n) {
            source_tile[threadIdx.x] = in[source_index];
        }
        __syncthreads();

        int tile_count = n - tile_start;
        if (tile_count > block_size) {
            tile_count = block_size;
        }

        if (i < n) {
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
