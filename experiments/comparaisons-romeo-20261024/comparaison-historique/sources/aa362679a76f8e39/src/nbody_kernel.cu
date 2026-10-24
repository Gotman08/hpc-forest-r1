// Structure de particule utilisée par le contrat du kernel.
struct Particle {
    float x, y, z;
    float vx, vy, vz;
    float mass;
};

// Chaque thread traite deux cibles et réutilise chaque source pour les deux.
extern "C" __global__ void nbody_step_naive(const Particle* in, Particle* out, int n, float dt) {
    const unsigned long long first =
        static_cast<unsigned long long>(blockIdx.x) * (2ULL * blockDim.x) + threadIdx.x;
    const unsigned long long second = first + blockDim.x;
    const unsigned long long count = static_cast<unsigned long long>(n);
    const bool valid0 = first < count;
    const bool valid1 = second < count;

    if (!valid0 && !valid1) return;

    const float G = 1.0f;
    const float softening = 0.001f;

    Particle p0;
    Particle p1;
    float fx0 = 0.0f, fy0 = 0.0f, fz0 = 0.0f;
    float fx1 = 0.0f, fy1 = 0.0f, fz1 = 0.0f;

    if (valid0) p0 = in[first];
    if (valid1) p1 = in[second];

    for (int j = 0; j < n; ++j) {
        const Particle source = in[j];

        if (valid0 && first != static_cast<unsigned long long>(j)) {
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

        if (valid1 && second != static_cast<unsigned long long>(j)) {
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
}
