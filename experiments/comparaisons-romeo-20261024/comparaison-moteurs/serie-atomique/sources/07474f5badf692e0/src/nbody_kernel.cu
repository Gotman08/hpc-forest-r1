struct Particle {
    float x, y, z;
    float vx, vy, vz;
    float mass;
};

extern "C" __global__ void nbody_step_naive(const Particle* in, Particle* out, int n, float dt) {
    const int targets_per_thread = 2;
    const int first = blockIdx.x * (targets_per_thread * blockDim.x) + threadIdx.x;
    if (first >= n) return;

    const int second = first + blockDim.x;
    const bool has_second = second < n;
    const Particle target0 = in[first];
    Particle target1;
    if (has_second) target1 = in[second];

    const float G = 1.0f;
    const float softening = 0.001f;
    float fx0 = 0.0f, fy0 = 0.0f, fz0 = 0.0f;
    float fx1 = 0.0f, fy1 = 0.0f, fz1 = 0.0f;

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
}
