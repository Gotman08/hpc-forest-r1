// Structure "Array of Structures" conservée pour respecter l'interface.
struct Particle {
    float x, y, z;
    float vx, vy, vz;
    float mass;
};

// Chaque thread traite une cible; le bloc charge des tuiles de sources partagées.
extern "C" __global__ void nbody_step_naive(const Particle* in, Particle* out, int n, float dt) {
    const int i = blockIdx.x * blockDim.x + threadIdx.x;
    const bool active = i < n;

    const float G = 1.0f;
    const float softening = 0.001f;
    const int tile_size = 512;

    extern __shared__ Particle source_tile[];

    Particle target;
    if (active) {
        target = in[i];
    }

    float fx = 0.0f;
    float fy = 0.0f;
    float fz = 0.0f;

    for (int tile_start = 0; tile_start < n;) {
        int tile_count = n - tile_start;
        if (tile_count > tile_size) {
            tile_count = tile_size;
        }

        // Avec 128 threads et une tuile de 512 éléments, chaque thread
        // charge jusqu'à quatre sources. La dernière tuile est bornée à n.
        for (int k = threadIdx.x; k < tile_count; k += blockDim.x) {
            source_tile[k] = in[tile_start + k];
        }
        __syncthreads();

        if (active) {
            for (int k = 0; k < tile_count; ++k) {
                const int j = tile_start + k;
                if (i == j) continue;

                const Particle source = source_tile[k];
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

        // Tous les threads, même ceux sans cible, atteignent cette barrière
        // avant que la tuile partagée soit réutilisée.
        __syncthreads();
        tile_start += tile_count;
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
