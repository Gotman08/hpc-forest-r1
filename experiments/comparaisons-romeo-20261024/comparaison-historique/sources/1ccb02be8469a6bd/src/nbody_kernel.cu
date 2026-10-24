struct Particle {
    float x, y, z;
    float vx, vy, vz;
    float mass;
};

extern "C" __global__ void nbody_step_naive(const Particle* in, Particle* out, int n, float dt) {
    // The configured tile is 2 * blockDim.x: each thread handles two outputs.
    const int i0 = blockIdx.x * (2 * blockDim.x) + threadIdx.x;
    const int i1 = i0 + blockDim.x;
    const bool active0 = i0 < n;
    const bool active1 = i1 < n;

    if (!active0 && !active1) return;

    const float G = 1.0f;
    const float softening = 0.001f;

    Particle p0;
    Particle p1;
    if (active0) p0 = in[i0];
    if (active1) p1 = in[i1];

    float fx0 = 0.0f, fy0 = 0.0f, fz0 = 0.0f;
    float fx1 = 0.0f, fy1 = 0.0f, fz1 = 0.0f;

    for (int j = 0; j < n; ++j) {
        const Particle source = in[j];
        const float sx = source.x;
        const float sy = source.y;
        const float sz = source.z;
        const float source_mass = source.mass;

        if (active0 && i0 != j) {
            const float dx = sx - p0.x;
            const float dy = sy - p0.y;
            const float dz = sz - p0.z;
            const float distSq = dx * dx + dy * dy + dz * dz + softening;
            const float dist = sqrtf(distSq);
            const float f = (G * p0.mass * source_mass) / (distSq * dist);
            fx0 += f * dx;
            fy0 += f * dy;
            fz0 += f * dz;
        }

        if (active1 && i1 != j) {
            const float dx = sx - p1.x;
            const float dy = sy - p1.y;
            const float dz = sz - p1.z;
            const float distSq = dx * dx + dy * dy + dz * dz + softening;
            const float dist = sqrtf(distSq);
            const float f = (G * p1.mass * source_mass) / (distSq * dist);
            fx1 += f * dx;
            fy1 += f * dy;
            fz1 += f * dz;
        }
    }

    if (active0) {
        p0.vx += (fx0 / p0.mass) * dt;
        p0.vy += (fy0 / p0.mass) * dt;
        p0.vz += (fz0 / p0.mass) * dt;
        p0.x += p0.vx * dt;
        p0.y += p0.vy * dt;
        p0.z += p0.vz * dt;
        out[i0] = p0;
    }

    if (active1) {
        p1.vx += (fx1 / p1.mass) * dt;
        p1.vy += (fy1 / p1.mass) * dt;
        p1.vz += (fz1 / p1.mass) * dt;
        p1.x += p1.vx * dt;
        p1.y += p1.vy * dt;
        p1.z += p1.vz * dt;
        out[i1] = p1;
    }
}
