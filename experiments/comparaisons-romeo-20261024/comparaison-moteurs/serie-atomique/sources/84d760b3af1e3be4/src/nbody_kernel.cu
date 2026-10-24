// Structure "Array of Structures" (AoS) : intuitive mais naïve sur GPU
// car elle empêche la coalescence parfaite des accès mémoire.
struct Particle {
    float x, y, z;
    float vx, vy, vz;
    float mass;
};

// Each thread computes two distinct targets. Adjacent lanes cover contiguous
// targets in each half of the block's target group.
extern "C" __global__ void nbody_step_naive(const Particle* in, Particle* out, int n, float dt) {
    const int targets_per_block = blockDim.x * 2;
    const int first = blockIdx.x * targets_per_block + threadIdx.x;
    const int second = first + blockDim.x;
    const bool valid0 = first < n;
    const bool valid1 = second < n;
    if (!valid0 && !valid1) return;

    const float G = 1.0f;
    const float softening = 0.001f;

    Particle p0;
    Particle p1;
    if (valid0) p0 = in[first];
    if (valid1) p1 = in[second];

    float fx0 = 0.0f;
    float fy0 = 0.0f;
    float fz0 = 0.0f;
    float fx1 = 0.0f;
    float fy1 = 0.0f;
    float fz1 = 0.0f;

    // Load each source position and mass once per iteration, then reuse those
    // register values for both target accumulations. No shared-memory tiling.
    for (int j = 0; j < n; j++) {
        const float sx = in[j].x;
        const float sy = in[j].y;
        const float sz = in[j].z;
        const float sourceMass = in[j].mass;

        if (valid0 && first != j) {
            float dx = sx - p0.x;
            float dy = sy - p0.y;
            float dz = sz - p0.z;

            float distSq = dx * dx + dy * dy + dz * dz + softening;
            float dist = sqrtf(distSq);

            float f = (G * p0.mass * sourceMass) / (distSq * dist);

            fx0 += f * dx;
            fy0 += f * dy;
            fz0 += f * dz;
        }

        if (valid1 && second != j) {
            float dx = sx - p1.x;
            float dy = sy - p1.y;
            float dz = sz - p1.z;

            float distSq = dx * dx + dy * dy + dz * dz + softening;
            float dist = sqrtf(distSq);

            float f = (G * p1.mass * sourceMass) / (distSq * dist);

            fx1 += f * dx;
            fy1 += f * dy;
            fz1 += f * dz;
        }
    }

    if (valid0) {
        p0.vx += (fx0 / p0.mass) * dt;
        p0.vy += (fy0 / p0.mass) * dt;
        p0.vz += (fz0 / p0.mass) * dt;

        p0.x += p0.vx * dt;
        p0.y += p0.vy * dt;
        p0.z += p0.vz * dt;

        out[first] = p0;
    }

    if (valid1) {
        p1.vx += (fx1 / p1.mass) * dt;
        p1.vy += (fy1 / p1.mass) * dt;
        p1.vz += (fz1 / p1.mass) * dt;

        p1.x += p1.vx * dt;
        p1.y += p1.vy * dt;
        p1.z += p1.vz * dt;

        out[second] = p1;
    }
}
