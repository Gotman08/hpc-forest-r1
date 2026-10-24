// Structure « Array of Structures » (AoS) d'entrée et de sortie.
struct Particle {
    float x, y, z;
    float vx, vy, vz;
    float mass;
};

// Tuiles SoA en mémoire partagée : chaque source est consommée dans l'ordre.
// Le bloc conserve 256 cibles et charge une tuile de 512 sources par passe.
extern "C" __global__ void nbody_step_naive(const Particle* in, Particle* out, int n, float dt) {
    constexpr int TILE_SIZE = 512;
    __shared__ float tile_x[TILE_SIZE];
    __shared__ float tile_y[TILE_SIZE];
    __shared__ float tile_z[TILE_SIZE];
    __shared__ float tile_mass[TILE_SIZE];

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

    // Tous les threads, y compris ceux de la queue, atteignent les deux barrières.
    for (int base = 0; base < n; base += TILE_SIZE) {
        // Chaque thread charge plusieurs sources si nécessaire; les accès restent contigus.
        for (int source_offset = lane; source_offset < TILE_SIZE; source_offset += block_size) {
            if (source_offset < n - base) {
                const Particle source = in[base + source_offset];
                tile_x[source_offset] = source.x;
                tile_y[source_offset] = source.y;
                tile_z[source_offset] = source.z;
                tile_mass[source_offset] = source.mass;
            }
        }
        __syncthreads();

        int tile_count = n - base;
        if (tile_count > TILE_SIZE) {
            tile_count = TILE_SIZE;
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
