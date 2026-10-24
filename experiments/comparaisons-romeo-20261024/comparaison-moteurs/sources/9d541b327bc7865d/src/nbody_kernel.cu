// Structure "Array of Structures" utilisée par l'interface du kernel.
struct Particle {
    float x, y, z;
    float vx, vy, vz;
    float mass;
};

// Chaque warp charge ses sources par lanes et les diffuse par shuffle,
// sans mémoire partagée. L'ordre des interactions reste croissant en j.
extern "C" __global__ void nbody_step_naive(const Particle* in, Particle* out, int n, float dt) {
    const int i = blockIdx.x * blockDim.x + threadIdx.x;
    const bool output_valid = i < n;

    Particle p;
    float target_x = 0.0f;
    float target_y = 0.0f;
    float target_z = 0.0f;
    float target_mass = 0.0f;
    if (output_valid) {
        p = in[i];
        target_x = p.x;
        target_y = p.y;
        target_z = p.z;
        target_mass = p.mass;
    }

    constexpr int warp_width = 32;
    constexpr unsigned int full_warp_mask = 0xffffffffu;
    const int lane = threadIdx.x % warp_width;
    const int tile_count = n / warp_width + ((n % warp_width) != 0);

    const float G = 1.0f;
    const float softening = 0.001f;
    float fx = 0.0f;
    float fy = 0.0f;
    float fz = 0.0f;

    // Pas de retour anticipé : les 32 lanes, y compris les sorties inactives,
    // participent à chaque shuffle avec le masque complet.
    for (int tile = 0; tile < tile_count; ++tile) {
        const int base = tile * warp_width;
        const int source_index = base + lane;
        float source_x = 0.0f;
        float source_y = 0.0f;
        float source_z = 0.0f;
        float source_mass = 0.0f;

        if (source_index < n) {
            source_x = in[source_index].x;
            source_y = in[source_index].y;
            source_z = in[source_index].z;
            source_mass = in[source_index].mass;
        }

        #pragma unroll
        for (int source_lane = 0; source_lane < warp_width; ++source_lane) {
            const int j = base + source_lane;
            const float xj = __shfl_sync(full_warp_mask, source_x, source_lane);
            const float yj = __shfl_sync(full_warp_mask, source_y, source_lane);
            const float zj = __shfl_sync(full_warp_mask, source_z, source_lane);
            const float massj = __shfl_sync(full_warp_mask, source_mass, source_lane);

            if (j < n && i != j) {
                const float dx = xj - target_x;
                const float dy = yj - target_y;
                const float dz = zj - target_z;

                const float distSq = dx * dx + dy * dy + dz * dz + softening;
                const float dist = sqrtf(distSq);
                const float f = (G * target_mass * massj) / (distSq * dist);

                fx += f * dx;
                fy += f * dy;
                fz += f * dz;
            }
        }
    }

    if (output_valid) {
        p.vx += (fx / p.mass) * dt;
        p.vy += (fy / p.mass) * dt;
        p.vz += (fz / p.mass) * dt;

        p.x += p.vx * dt;
        p.y += p.vy * dt;
        p.z += p.vz * dt;

        out[i] = p;
    }
}
