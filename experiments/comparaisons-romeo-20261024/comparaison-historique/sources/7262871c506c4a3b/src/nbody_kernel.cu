// Structure "Array of Structures" (AoS) : intuitive mais naïve sur GPU
// car elle empêche la coalescence parfaite des accès mémoire.
struct Particle {
    float x, y, z;
    float vx, vy, vz;
    float mass;
};

// Chaque warp charge un tile de sources par lanes, puis diffuse chaque
// source par shuffle aux lanes qui accumulent leurs cibles. Le tile suivant
// est préchargé pendant le calcul du tile courant.
extern "C" __global__ void nbody_step_naive(const Particle* in, Particle* out, int n, float dt) {
    int i = blockIdx.x * blockDim.x + threadIdx.x;
    int lane = threadIdx.x & 31;
    bool target_valid = i < n;

    // Ne pas faire sortir les lanes invalides : elles participent aux shuffles
    // nécessaires aux autres cibles du warp.
    Particle p = {};
    if (target_valid) p = in[i];

    const float G = 1.0f;
    const float softening = 0.001f;
    float fx = 0.0f;
    float fy = 0.0f;
    float fz = 0.0f;

    int base = 0;
    int valid_sources = n < 32 ? n : 32;
    float sx_lane = 0.0f;
    float sy_lane = 0.0f;
    float sz_lane = 0.0f;
    float sm_lane = 0.0f;
    if (lane < valid_sources) {
        const Particle& source = in[lane];
        sx_lane = source.x;
        sy_lane = source.y;
        sz_lane = source.z;
        sm_lane = source.mass;
    }

    // Le parcours par tiles conserve l'ordre croissant des indices source.
    while (base < n) {
        int remaining = n - base;
        int next_sources = remaining > 32 ? remaining - 32 : 0;
        if (next_sources > 32) next_sources = 32;

        // Charger par lane le prochain tile avant les shuffles et le calcul
        // du tile courant afin de pouvoir recouvrir une partie de la latence.
        float next_sx_lane = 0.0f;
        float next_sy_lane = 0.0f;
        float next_sz_lane = 0.0f;
        float next_sm_lane = 0.0f;
        if (lane < next_sources) {
            const Particle& next_source = in[base + 32 + lane];
            next_sx_lane = next_source.x;
            next_sy_lane = next_source.y;
            next_sz_lane = next_source.z;
            next_sm_lane = next_source.mass;
        }

        for (int s = 0; s < 32; ++s) {
            float sx = __shfl_sync(0xffffffffu, sx_lane, s);
            float sy = __shfl_sync(0xffffffffu, sy_lane, s);
            float sz = __shfl_sync(0xffffffffu, sz_lane, s);
            float sm = __shfl_sync(0xffffffffu, sm_lane, s);

            if (target_valid && s < valid_sources) {
                int j = base + s;
                if (i != j) {
                    float dx = sx - p.x;
                    float dy = sy - p.y;
                    float dz = sz - p.z;
                    float distSq = dx * dx + dy * dy + dz * dz + softening;
                    float dist = sqrtf(distSq);
                    float f = (G * p.mass * sm) / (distSq * dist);
                    fx += f * dx;
                    fy += f * dy;
                    fz += f * dz;
                }
            }
        }

        if (remaining <= 32) break;
        sx_lane = next_sx_lane;
        sy_lane = next_sy_lane;
        sz_lane = next_sz_lane;
        sm_lane = next_sm_lane;
        valid_sources = next_sources;
        base += 32;
    }

    if (target_valid) {
        p.vx += (fx / p.mass) * dt;
        p.vy += (fy / p.mass) * dt;
        p.vz += (fz / p.mass) * dt;
        p.x += p.vx * dt;
        p.y += p.vy * dt;
        p.z += p.vz * dt;
        out[i] = p;
    }
}
