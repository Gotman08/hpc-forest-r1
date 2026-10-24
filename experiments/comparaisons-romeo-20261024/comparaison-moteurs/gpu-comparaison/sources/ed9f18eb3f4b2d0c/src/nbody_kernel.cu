struct Particle {
    float x, y, z;
    float vx, vy, vz;
    float mass;
};

extern "C" __global__ void nbody_step_naive(const Particle* in, Particle* out, int n, float dt) {
    const int targets_per_thread = 3;
    const int first = blockIdx.x * (targets_per_thread * blockDim.x) + threadIdx.x;
    if (first >= n) return;

    const int second = first + blockDim.x;
    const int third = second + blockDim.x;
    const bool has_second = second < n;
    const bool has_third = third < n;
    const Particle target0 = in[first];
    Particle target1;
    Particle target2;
    if (has_second) target1 = in[second];
    if (has_third) target2 = in[third];

    const float G = 1.0f;
    const float softening = 0.001f;
    float fx0 = 0.0f, fy0 = 0.0f, fz0 = 0.0f;
    float fx1 = 0.0f, fy1 = 0.0f, fz1 = 0.0f;
    float fx2 = 0.0f, fy2 = 0.0f, fz2 = 0.0f;

    for (int j = 0; j < n; ++j) {
        const Particle source = in[j];

        if (first != j) {
            const float dx = source.x - target0.x;
            const float dy = source.y - target0.y;
            const float dz = source.z - target0.z;
            const float distSq = dx * dx + dy * dy + dz * dz + softening;
            const float dist = sqrtf(distSq);
            const float f = (G * target0.mass * source.mass) / (distSq * dist);
            fx0 += f * dx;
            fy0 += f * dy;
            fz0 += f * dz;
        }

        if (has_second && second != j) {
            const float dx = source.x - target1.x;
            const float dy = source.y - target1.y;
            const float dz = source.z - target1.z;
            const float distSq = dx * dx + dy * dy + dz * dz + softening;
            const float dist = sqrtf(distSq);
            const float f = (G * target1.mass * source.mass) / (distSq * dist);
            fx1 += f * dx;
            fy1 += f * dy;
            fz1 += f * dz;
        }

        if (has_third && third != j) {
            const float dx = source.x - target2.x;
            const float dy = source.y - target2.y;
            const float dz = source.z - target2.z;
            const float distSq = dx * dx + dy * dy + dz * dz + softening;
            const float dist = sqrtf(distSq);
            const float f = (G * target2.mass * source.mass) / (distSq * dist);
            fx2 += f * dx;
            fy2 += f * dy;
            fz2 += f * dz;
        }
    }

    Particle result0 = target0;
    result0.vx += (fx0 / result0.mass) * dt;
    result0.vy += (fy0 / result0.mass) * dt;
    result0.vz += (fz0 / result0.mass) * dt;
    result0.x += result0.vx * dt;
    result0.y += result0.vy * dt;
    result0.z += result0.vz * dt;
    out[first] = result0;

    if (has_second) {
        Particle result1 = target1;
        result1.vx += (fx1 / result1.mass) * dt;
        result1.vy += (fy1 / result1.mass) * dt;
        result1.vz += (fz1 / result1.mass) * dt;
        result1.x += result1.vx * dt;
        result1.y += result1.vy * dt;
        result1.z += result1.vz * dt;
        out[second] = result1;
    }

    if (has_third) {
        Particle result2 = target2;
        result2.vx += (fx2 / result2.mass) * dt;
        result2.vy += (fy2 / result2.mass) * dt;
        result2.vz += (fz2 / result2.mass) * dt;
        result2.x += result2.vx * dt;
        result2.y += result2.vy * dt;
        result2.z += result2.vz * dt;
        out[third] = result2;
    }
}
