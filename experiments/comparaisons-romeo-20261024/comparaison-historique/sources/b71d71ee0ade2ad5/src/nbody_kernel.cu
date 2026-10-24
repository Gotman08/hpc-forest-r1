struct Particle {
    float x, y, z;
    float vx, vy, vz;
    float mass;
};

extern "C" __global__ void nbody_step_naive(const Particle* in, Particle* out, int n, float dt) {
    const int first = (blockIdx.x * blockDim.x + threadIdx.x) * 2;
    if (first >= n) return;

    const int second = first + 1;
    const float G = 1.0f;
    const float softening = 0.001f;

    Particle p0 = in[first];
    Particle p1;
    if (second < n) p1 = in[second];

    float fx0 = 0.0f;
    float fy0 = 0.0f;
    float fz0 = 0.0f;
    float fx1 = 0.0f;
    float fy1 = 0.0f;
    float fz1 = 0.0f;

    for (int j = 0; j < n; ++j) {
        const float sx = in[j].x;
        const float sy = in[j].y;
        const float sz = in[j].z;
        const float source_mass = in[j].mass;

        if (first != j) {
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

        if (second < n && second != j) {
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

    p0.vx += (fx0 / p0.mass) * dt;
    p0.vy += (fy0 / p0.mass) * dt;
    p0.vz += (fz0 / p0.mass) * dt;
    p0.x += p0.vx * dt;
    p0.y += p0.vy * dt;
    p0.z += p0.vz * dt;
    out[first] = p0;

    if (second < n) {
        p1.vx += (fx1 / p1.mass) * dt;
        p1.vy += (fy1 / p1.mass) * dt;
        p1.vz += (fz1 / p1.mass) * dt;
        p1.x += p1.vx * dt;
        p1.y += p1.vy * dt;
        p1.z += p1.vz * dt;
        out[second] = p1;
    }
}
