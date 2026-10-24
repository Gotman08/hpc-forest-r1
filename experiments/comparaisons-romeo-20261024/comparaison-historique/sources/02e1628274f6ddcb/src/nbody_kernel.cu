struct Particle {
    float x, y, z;
    float vx, vy, vz;
    float mass;
};

extern "C" __global__ void nbody_step_naive(const Particle* in, Particle* out, int n, float dt) {
    if (n <= 0) return;

    const unsigned int count = static_cast<unsigned int>(n);
    const unsigned int i0 = blockIdx.x * (blockDim.x * 4u) + threadIdx.x;
    const unsigned int i1 = i0 + blockDim.x;
    const unsigned int i2 = i1 + blockDim.x;
    const unsigned int i3 = i2 + blockDim.x;

    if (i0 >= count) return;
    const bool valid1 = i1 < count;
    const bool valid2 = i2 < count;
    const bool valid3 = i3 < count;

    Particle p0 = in[i0];
    Particle p1;
    Particle p2;
    Particle p3;
    if (valid1) p1 = in[i1];
    if (valid2) p2 = in[i2];
    if (valid3) p3 = in[i3];

    const float G = 1.0f;
    const float softening = 0.001f;
    float fx0 = 0.0f, fy0 = 0.0f, fz0 = 0.0f;
    float fx1 = 0.0f, fy1 = 0.0f, fz1 = 0.0f;
    float fx2 = 0.0f, fy2 = 0.0f, fz2 = 0.0f;
    float fx3 = 0.0f, fy3 = 0.0f, fz3 = 0.0f;

    for (int j = 0; j < n; ++j) {
        const Particle source = in[j];

        if (i0 != static_cast<unsigned int>(j)) {
            const float dx = source.x - p0.x;
            const float dy = source.y - p0.y;
            const float dz = source.z - p0.z;
            const float distSq = dx * dx + dy * dy + dz * dz + softening;
            const float dist = sqrtf(distSq);
            const float f = (G * p0.mass * source.mass) / (distSq * dist);
            fx0 += f * dx;
            fy0 += f * dy;
            fz0 += f * dz;
        }

        if (valid1 && i1 != static_cast<unsigned int>(j)) {
            const float dx = source.x - p1.x;
            const float dy = source.y - p1.y;
            const float dz = source.z - p1.z;
            const float distSq = dx * dx + dy * dy + dz * dz + softening;
            const float dist = sqrtf(distSq);
            const float f = (G * p1.mass * source.mass) / (distSq * dist);
            fx1 += f * dx;
            fy1 += f * dy;
            fz1 += f * dz;
        }

        if (valid2 && i2 != static_cast<unsigned int>(j)) {
            const float dx = source.x - p2.x;
            const float dy = source.y - p2.y;
            const float dz = source.z - p2.z;
            const float distSq = dx * dx + dy * dy + dz * dz + softening;
            const float dist = sqrtf(distSq);
            const float f = (G * p2.mass * source.mass) / (distSq * dist);
            fx2 += f * dx;
            fy2 += f * dy;
            fz2 += f * dz;
        }

        if (valid3 && i3 != static_cast<unsigned int>(j)) {
            const float dx = source.x - p3.x;
            const float dy = source.y - p3.y;
            const float dz = source.z - p3.z;
            const float distSq = dx * dx + dy * dy + dz * dz + softening;
            const float dist = sqrtf(distSq);
            const float f = (G * p3.mass * source.mass) / (distSq * dist);
            fx3 += f * dx;
            fy3 += f * dy;
            fz3 += f * dz;
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

    if (valid2) {
        p2.vx += (fx2 / p2.mass) * dt;
        p2.vy += (fy2 / p2.mass) * dt;
        p2.vz += (fz2 / p2.mass) * dt;
        p2.x += p2.vx * dt;
        p2.y += p2.vy * dt;
        p2.z += p2.vz * dt;
        out[i2] = p2;
    }

    if (valid3) {
        p3.vx += (fx3 / p3.mass) * dt;
        p3.vy += (fy3 / p3.mass) * dt;
        p3.vz += (fz3 / p3.mass) * dt;
        p3.x += p3.vx * dt;
        p3.y += p3.vy * dt;
        p3.z += p3.vz * dt;
        out[i3] = p3;
    }
}
