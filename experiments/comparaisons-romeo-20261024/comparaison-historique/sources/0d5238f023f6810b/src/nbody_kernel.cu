// Structure "Array of Structures" (AoS) : intuitive mais naïve sur GPU
// car elle empêche la coalescence parfaite des accès mémoire.
struct Particle {
    float x, y, z;
    float vx, vy, vz;
    float mass;
};

// Chaque warp charge un tile de sources par lanes, puis diffuse chaque
// source par shuffle aux lanes qui accumulent leurs cibles.
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

    // Le parcours par tiles conserve l'ordre croissant des indices source.
    for (int base = 0; base < n; ) {
        int source_index = base + lane;
        float sx_lane = 0.0f;
        float sy_lane = 0.0f;
        float sz_lane = 0.0f;
        float sm_lane = 0.0f;
        if (source_index < n) {
            const Particle& source = in[source_index];
            sx_lane = source.x;
            sy_lane = source.y;
            sz_lane = source.z;
            sm_lane = source.mass;
        }

        for (int s = 0; s < 32; ++s) {
            int j = base + s;
            float sx = __shfl_sync(0xffffffffu, sx_lane, s);
            float sy = __shfl_sync(0xffffffffu, sy_lane, s);
            float sz = __shfl_sync(0xffffffffu, sz_lane, s);
            float sm = __shfl_sync(0xffffffffu, sm_lane, s);

            if (target_valid && j < n && i != j) {
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

        if (n - base <= 32) break;
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
