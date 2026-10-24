struct Particle {
    float x, y, z;
    float vx, vy, vz;
    float mass;
};

extern "C" __global__ void nbody_step_naive(const Particle* in, Particle* out, int n, float dt) {
    // Each CTA covers items_per_block = 2 * blockDim.x outputs.
    const int first = static_cast<int>(blockIdx.x * (2 * blockDim.x)) + threadIdx.x;
    const int second = first + static_cast<int>(blockDim.x);
    const bool valid_first = first < n;
    const bool valid_second = second < n;
    if (!valid_first && !valid_second) return;

    Particle p0;
    Particle p1;
    if (valid_first) p0 = in[first];
    if (valid_second) p1 = in[second];

    const float G = 1.0f;
    const float softening = 0.001f;
    float fx0 = 0.0f;
    float fy0 = 0.0f;
    float fz0 = 0.0f;
    float fx1 = 0.0f;
    float fy1 = 0.0f;
    float fz1 = 0.0f;

    // Reuse each source particle's coordinates and mass for both outputs.
    for (int j = 0; j < n; ++j) {
        const float sx = in[j].x;
        const float sy = in[j].y;
        const float sz = in[j].z;
        const float smass = in[j].mass;

        if (valid_first && first != j) {
            const float dx = sx - p0.x;
            const float dy = sy - p0.y;
            const float dz = sz - p0.z;
            const float distSq = dx * dx + dy * dy + dz * dz + softening;
            const float dist = sqrtf(distSq);
            const float f = (G * p0.mass * smass) / (distSq * dist);
            fx0 += f * dx;
            fy0 += f * dy;
            fz0 += f * dz;
        }

        if (valid_second && second != j) {
            const float dx = sx - p1.x;
            const float dy = sy - p1.y;
            const float dz = sz - p1.z;
            const float distSq = dx * dx + dy * dy + dz * dz + softening;
            const float dist = sqrtf(distSq);
            const float f = (G * p1.mass * smass) / (distSq * dist);
            fx1 += f * dx;
            fy1 += f * dy;
            fz1 += f * dz;
        }
    }

    if (valid_first) {
        p0.vx += (fx0 / p0.mass) * dt;
        p0.vy += (fy0 / p0.mass) * dt;
        p0.vz += (fz0 / p0.mass) * dt;
        p0.x += p0.vx * dt;
        p0.y += p0.vy * dt;
        p0.z += p0.vz * dt;
        out[first] = p0;
    }

    if (valid_second) {
        p1.vx += (fx1 / p1.mass) * dt;
        p1.vy += (fy1 / p1.mass) * dt;
        p1.vz += (fz1 / p1.mass) * dt;
        p1.x += p1.vx * dt;
        p1.y += p1.vy * dt;
        p1.z += p1.vz * dt;
        out[second] = p1;
    }
}
