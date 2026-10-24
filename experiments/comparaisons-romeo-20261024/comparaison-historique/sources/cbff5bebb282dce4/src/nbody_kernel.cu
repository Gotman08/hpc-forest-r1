struct Particle {
    float x, y, z;
    float vx, vy, vz;
    float mass;
};

extern "C" __global__ void nbody_step_naive(const Particle* in, Particle* out, int n, float dt) {
    const long long block_base = static_cast<long long>(blockIdx.x) *
                                 static_cast<long long>(blockDim.x) * 2LL;
    const long long i0 = block_base + static_cast<long long>(threadIdx.x);
    const long long i1 = i0 + static_cast<long long>(blockDim.x);

    const bool valid0 = i0 < n;
    const bool valid1 = i1 < n;
    if (!valid0 && !valid1) return;

    Particle p0;
    Particle p1;
    if (valid0) p0 = in[i0];
    if (valid1) p1 = in[i1];

    float fx0 = 0.0f, fy0 = 0.0f, fz0 = 0.0f;
    float fx1 = 0.0f, fy1 = 0.0f, fz1 = 0.0f;

    const float G = 1.0f;
    const float softening = 0.001f;

    for (int j = 0; j < n; ++j) {
        const Particle source = in[j];

        if (valid0 && i0 != j) {
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

        if (valid1 && i1 != j) {
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
    }

    if (valid0) {
        p0.vx += (fx0 / p0.mass) * dt;
        p0.vy += (fy0 / p0.mass) * dt;
        p0.vz += (fz0 / p0.mass) * dt;
        p0.x += p0.vx * dt;
        p0.y += p0.vy * dt;
        p0.z += p0.vz * dt;
        out[i0] = p0;
    }

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
