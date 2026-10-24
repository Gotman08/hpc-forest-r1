struct Particle {
    float x, y, z;
    float vx, vy, vz;
    float mass;
};

extern "C" __global__ void nbody_step_naive(const Particle* in, Particle* out, int n, float dt) {
    const unsigned int first = blockIdx.x * (2u * blockDim.x) + threadIdx.x;
    const unsigned int limit = static_cast<unsigned int>(n);
    if (first >= limit) return;

    const unsigned int second = first + blockDim.x;
    const bool has_second = second < limit;

    const float G = 1.0f;
    const float softening = 0.001f;

    Particle p0 = in[first];
    Particle p1;
    if (has_second) p1 = in[second];

    float fx0 = 0.0f;
    float fy0 = 0.0f;
    float fz0 = 0.0f;
    float fx1 = 0.0f;
    float fy1 = 0.0f;
    float fz1 = 0.0f;

    for (int j = 0; j < n; j++) {
        const float source_x = in[j].x;
        const float source_y = in[j].y;
        const float source_z = in[j].z;
        const float source_mass = in[j].mass;
        const unsigned int source_index = static_cast<unsigned int>(j);

        if (first != source_index) {
            const float dx = source_x - p0.x;
            const float dy = source_y - p0.y;
            const float dz = source_z - p0.z;
            const float distSq = dx * dx + dy * dy + dz * dz + softening;
            const float dist = sqrtf(distSq);
            const float f = (G * p0.mass * source_mass) / (distSq * dist);
            fx0 += f * dx;
            fy0 += f * dy;
            fz0 += f * dz;
        }

        if (has_second && second != source_index) {
            const float dx = source_x - p1.x;
            const float dy = source_y - p1.y;
            const float dz = source_z - p1.z;
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

    if (has_second) {
        p1.vx += (fx1 / p1.mass) * dt;
        p1.vy += (fy1 / p1.mass) * dt;
        p1.vz += (fz1 / p1.mass) * dt;
        p1.x += p1.vx * dt;
        p1.y += p1.vy * dt;
        p1.z += p1.vz * dt;
        out[second] = p1;
    }
}
