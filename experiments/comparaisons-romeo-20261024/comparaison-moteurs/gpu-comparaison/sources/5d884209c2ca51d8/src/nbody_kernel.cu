// Two adjacent targets per thread: block=128 and items_per_block=256 in
// src/launch.json, so each block covers 128 * targets_per_thread targets.
struct Particle {
    float x, y, z;
    float vx, vy, vz;
    float mass;
};

extern "C" __global__ void nbody_step_naive(const Particle* in, Particle* out, int n, float dt) {
    constexpr unsigned int targets_per_thread = 2;
    const unsigned int thread_index = blockIdx.x * blockDim.x + threadIdx.x;
    const unsigned int i0u = thread_index * targets_per_thread;
    if (i0u >= (unsigned int)n) return;

    const int i0 = (int)i0u;
    const bool valid1 = i0u + 1u < (unsigned int)n;
    const int i1 = valid1 ? (int)(i0u + 1u) : 0;

    Particle p0 = in[i0];
    Particle p1;
    if (valid1) p1 = in[i1];

    const float G = 1.0f;
    const float softening = 0.001f;
    float fx0 = 0.0f;
    float fy0 = 0.0f;
    float fz0 = 0.0f;
    float fx1 = 0.0f;
    float fy1 = 0.0f;
    float fz1 = 0.0f;

    for (int j = 0; j < n; j++) {
        const float sx = in[j].x;
        const float sy = in[j].y;
        const float sz = in[j].z;
        const float source_mass = in[j].mass;

        if (i0 != j) {
            const float dx0 = sx - p0.x;
            const float dy0 = sy - p0.y;
            const float dz0 = sz - p0.z;
            const float distSq0 = dx0 * dx0 + dy0 * dy0 + dz0 * dz0 + softening;
            const float dist0 = sqrtf(distSq0);
            const float f0 = (G * p0.mass * source_mass) / (distSq0 * dist0);
            fx0 += f0 * dx0;
            fy0 += f0 * dy0;
            fz0 += f0 * dz0;
        }

        if (valid1 && i1 != j) {
            const float dx1 = sx - p1.x;
            const float dy1 = sy - p1.y;
            const float dz1 = sz - p1.z;
            const float distSq1 = dx1 * dx1 + dy1 * dy1 + dz1 * dz1 + softening;
            const float dist1 = sqrtf(distSq1);
            const float f1 = (G * p1.mass * source_mass) / (distSq1 * dist1);
            fx1 += f1 * dx1;
            fy1 += f1 * dy1;
            fz1 += f1 * dz1;
        }
    }

    p0.vx += (fx0 / p0.mass) * dt;
    p0.vy += (fy0 / p0.mass) * dt;
    p0.vz += (fz0 / p0.mass) * dt;
    p0.x += p0.vx * dt;
    p0.y += p0.vy * dt;
    p0.z += p0.vz * dt;
    out[i0] = p0;

    if (valid1) {
        p1.vx += (fx1 / p1.mass) * dt;
        p1.vy += (fy1 / p1.mass) * dt;
        p1.vz += (fz1 / p1.mass) * dt;
        p1.x += p1.vx * dt;
        p1.y += p1.vy * dt;
        p1.z += p1.vz * dt;
        out[i1] = p1;
    }
}
