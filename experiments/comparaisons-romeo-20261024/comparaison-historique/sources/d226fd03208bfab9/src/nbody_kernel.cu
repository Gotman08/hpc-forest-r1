struct Particle {
    float x, y, z;
    float vx, vy, vz;
    float mass;
};

// Each thread updates up to four consecutive outputs. One source particle's
// values are loaded once per source iteration and reused for all valid targets.
extern "C" __global__ void nbody_step_naive(const Particle* in, Particle* out, int n, float dt) {
    const long long first = (static_cast<long long>(blockIdx.x) * blockDim.x + threadIdx.x) * 4LL;
    if (first >= n) return;

    const long long second = first + 1;
    const long long third = first + 2;
    const long long fourth = first + 3;
    const bool has_second = second < n;
    const bool has_third = third < n;
    const bool has_fourth = fourth < n;
    const float G = 1.0f;
    const float softening = 0.001f;

    Particle p0 = in[first];
    Particle p1;
    Particle p2;
    Particle p3;
    if (has_second) p1 = in[second];
    if (has_third) p2 = in[third];
    if (has_fourth) p3 = in[fourth];

    float fx0 = 0.0f, fy0 = 0.0f, fz0 = 0.0f;
    float fx1 = 0.0f, fy1 = 0.0f, fz1 = 0.0f;
    float fx2 = 0.0f, fy2 = 0.0f, fz2 = 0.0f;
    float fx3 = 0.0f, fy3 = 0.0f, fz3 = 0.0f;

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

        if (has_second && second != j) {
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

        if (has_third && third != j) {
            const float dx = sx - p2.x;
            const float dy = sy - p2.y;
            const float dz = sz - p2.z;
            const float distSq = dx * dx + dy * dy + dz * dz + softening;
            const float dist = sqrtf(distSq);
            const float f = (G * p2.mass * source_mass) / (distSq * dist);
            fx2 += f * dx;
            fy2 += f * dy;
            fz2 += f * dz;
        }

        if (has_fourth && fourth != j) {
            const float dx = sx - p3.x;
            const float dy = sy - p3.y;
            const float dz = sz - p3.z;
            const float distSq = dx * dx + dy * dy + dz * dz + softening;
            const float dist = sqrtf(distSq);
            const float f = (G * p3.mass * source_mass) / (distSq * dist);
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
    out[first] = p0;

    if (has_second) {
        p1.vx += (fx1 / p1.mass) * dt;
        p1.vy += (fy1 / p1.mass) * dt;
        p1.vz += (fz1 / p1.mass) * dt;
        p1.x += p1.vx * dt;
        p1.y += p1.vy * dt;
        p1.z += p1.vz * dt;
        out[second] = p1;
    }

    if (has_third) {
        p2.vx += (fx2 / p2.mass) * dt;
        p2.vy += (fy2 / p2.mass) * dt;
        p2.vz += (fz2 / p2.mass) * dt;
        p2.x += p2.vx * dt;
        p2.y += p2.vy * dt;
        p2.z += p2.vz * dt;
        out[third] = p2;
    }

    if (has_fourth) {
        p3.vx += (fx3 / p3.mass) * dt;
        p3.vy += (fy3 / p3.mass) * dt;
        p3.vz += (fz3 / p3.mass) * dt;
        p3.x += p3.vx * dt;
        p3.y += p3.vy * dt;
        p3.z += p3.vz * dt;
        out[fourth] = p3;
    }
}
