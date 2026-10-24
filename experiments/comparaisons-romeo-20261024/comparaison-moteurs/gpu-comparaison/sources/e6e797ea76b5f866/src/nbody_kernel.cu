struct Particle {
    float x, y, z;
    float vx, vy, vz;
    float mass;
};

// Each thread computes three distinct targets and reuses source values in registers.
// Adjacent lanes cover contiguous targets in each 128-target section.
extern "C" __global__ void nbody_step_naive(const Particle* in, Particle* out, int n, float dt) {
    const int first = blockIdx.x * (blockDim.x * 3) + threadIdx.x;
    const int second = first + blockDim.x;
    const int third = second + blockDim.x;
    const bool valid0 = first < n;
    const bool valid1 = second < n;
    const bool valid2 = third < n;
    if (!valid0 && !valid1 && !valid2) return;

    const float G = 1.0f;
    const float softening = 0.001f;

    Particle p0;
    Particle p1;
    Particle p2;
    if (valid0) p0 = in[first];
    if (valid1) p1 = in[second];
    if (valid2) p2 = in[third];

    float fx0 = 0.0f;
    float fy0 = 0.0f;
    float fz0 = 0.0f;
    float fx1 = 0.0f;
    float fy1 = 0.0f;
    float fz1 = 0.0f;
    float fx2 = 0.0f;
    float fy2 = 0.0f;
    float fz2 = 0.0f;

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

        if (valid2 && third != j) {
            float dx = sx - p2.x;
            float dy = sy - p2.y;
            float dz = sz - p2.z;
            float distSq = dx * dx + dy * dy + dz * dz + softening;
            float dist = sqrtf(distSq);
            float f = (G * p2.mass * sourceMass) / (distSq * dist);
            fx2 += f * dx;
            fy2 += f * dy;
            fz2 += f * dz;
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

    if (valid2) {
        p2.vx += (fx2 / p2.mass) * dt;
        p2.vy += (fy2 / p2.mass) * dt;
        p2.vz += (fz2 / p2.mass) * dt;
        p2.x += p2.vx * dt;
        p2.y += p2.vy * dt;
        p2.z += p2.vz * dt;
        out[third] = p2;
    }
}
