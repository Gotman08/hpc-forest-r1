// Structure de particule d'entrée et de sortie (AoS).
struct Particle {
    float x, y, z;
    float vx, vy, vz;
    float mass;
};

// Tuilage des sources en mémoire partagée, avec une disposition SoA.
// Le lancement utilise un bloc de 256 threads, soit une tuile de 256 sources.
extern "C" __global__ void nbody_step_naive(const Particle* in, Particle* out, int n, float dt) {
    __shared__ float tile_x[256];
    __shared__ float tile_y[256];
    __shared__ float tile_z[256];
    __shared__ float tile_mass[256];

    const int lane = static_cast<int>(threadIdx.x);
    const int block_size = static_cast<int>(blockDim.x);
    const int i = static_cast<int>(blockIdx.x) * block_size + lane;
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

    // Tous les threads participent aux barrières, y compris ceux de la queue.
    for (int base = 0; base < n; base += block_size) {
        const int source_index = base + lane;
        if (source_index < n) {
            const Particle source = in[source_index];
            tile_x[lane] = source.x;
            tile_y[lane] = source.y;
            tile_z[lane] = source.z;
            tile_mass[lane] = source.mass;
        }
        __syncthreads();

        int tile_count = n - base;
        if (tile_count > block_size) {
            tile_count = block_size;
        }

        if (active) {
            for (int offset = 0; offset < tile_count; ++offset) {
                const int j = base + offset;
                if (i == j) {
                    continue;
                }

                const float dx = tile_x[offset] - target.x;
                const float dy = tile_y[offset] - target.y;
                const float dz = tile_z[offset] - target.z;

                const float distSq = dx * dx + dy * dy + dz * dz + softening;
                const float dist = sqrtf(distSq);
                const float f = (G * target.mass * tile_mass[offset]) / (distSq * dist);

                fx += f * dx;
                fy += f * dy;
                fz += f * dz;
            }
        }
        __syncthreads();
    }

    if (!active) {
        return;
    }

    Particle p = target;
    p.vx += (fx / p.mass) * dt;
    p.vy += (fy / p.mass) * dt;
    p.vz += (fz / p.mass) * dt;

    p.x += p.vx * dt;
    p.y += p.vy * dt;
    p.z += p.vz * dt;

    out[i] = p;
}
