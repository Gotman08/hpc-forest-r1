// Particle positions, velocities, and mass use an array-of-structures layout.
struct Particle {
    float x, y, z;
    float vx, vy, vz;
    float mass;
};

// Each warp loads a source tile by lane, then broadcasts its fields to the
// target lanes. All lanes in a participating warp execute every shuffle.
extern "C" __global__ void nbody_step_naive(const Particle* in, Particle* out, int n, float dt) {
    const int i = blockIdx.x * blockDim.x + threadIdx.x;
    const int lane = threadIdx.x & 31;
    const int warp_first_target = i - lane;

    // This is warp-uniform, so no lane in a participating warp exits early.
    if (warp_first_target >= n) return;

    const bool target_valid = i < n;
    Particle p;
    if (target_valid) p = in[i];

    const float G = 1.0f;
    const float softening = 0.001f;
    float fx = 0.0f;
    float fy = 0.0f;
    float fz = 0.0f;

    int source_base = 0;
    // Full tiles need no per-source validity test: every lane has a valid
    // source to load and every broadcast contributes for valid targets.
    while (n - source_base >= 32) {
        float tile_x = in[source_base + lane].x;
        float tile_y = in[source_base + lane].y;
        float tile_z = in[source_base + lane].z;
        float tile_mass = in[source_base + lane].mass;

        #pragma unroll 32
        for (int k = 0; k < 32; ++k) {
            const float sx = __shfl_sync(0xffffffffu, tile_x, k);
            const float sy = __shfl_sync(0xffffffffu, tile_y, k);
            const float sz = __shfl_sync(0xffffffffu, tile_z, k);
            const float source_mass = __shfl_sync(0xffffffffu, tile_mass, k);

            const int j = source_base + k;
            if (target_valid && i != j) {
                const float dx = sx - p.x;
                const float dy = sy - p.y;
                const float dz = sz - p.z;

                const float distSq = dx * dx + dy * dy + dz * dz + softening;
                const float dist = sqrtf(distSq);
                const float f = (G * p.mass * source_mass) / (distSq * dist);

                fx += f * dx;
                fy += f * dy;
                fz += f * dz;
            }
        }

        source_base += 32;
    }

    // Keep the partial tail separate so invalid source lanes are masked while
    // still participating in every shuffle with the full warp mask.
    const int remaining = n - source_base;
    if (remaining > 0) {
        float tile_x = 0.0f;
        float tile_y = 0.0f;
        float tile_z = 0.0f;
        float tile_mass = 0.0f;
        if (lane < remaining) {
            const int source_index = source_base + lane;
            tile_x = in[source_index].x;
            tile_y = in[source_index].y;
            tile_z = in[source_index].z;
            tile_mass = in[source_index].mass;
        }

        #pragma unroll 32
        for (int k = 0; k < 32; ++k) {
            const float sx = __shfl_sync(0xffffffffu, tile_x, k);
            const float sy = __shfl_sync(0xffffffffu, tile_y, k);
            const float sz = __shfl_sync(0xffffffffu, tile_z, k);
            const float source_mass = __shfl_sync(0xffffffffu, tile_mass, k);

            if (k < remaining) {
                const int j = source_base + k;
                if (target_valid && i != j) {
                    const float dx = sx - p.x;
                    const float dy = sy - p.y;
                    const float dz = sz - p.z;

                    const float distSq = dx * dx + dy * dy + dz * dz + softening;
                    const float dist = sqrtf(distSq);
                    const float f = (G * p.mass * source_mass) / (distSq * dist);

                    fx += f * dx;
                    fy += f * dy;
                    fz += f * dz;
                }
            }
        }
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
