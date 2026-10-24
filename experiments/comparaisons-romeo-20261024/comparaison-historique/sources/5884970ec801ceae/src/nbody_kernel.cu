// Structure "Array of Structures" (AoS) : intuitive mais naïve sur GPU
// car elle empêche la coalescence parfaite des accès mémoire.
struct Particle {
    float x, y, z;
    float vx, vy, vz;
    float mass;
};

// Chaque thread calcule deux sorties et réutilise les valeurs de la particule
// source courante pour les deux accumulations.
extern "C" __global__ void nbody_step_naive(const Particle* in, Particle* out, int n, float dt) {
    const int blockOutputSpan = 2 * static_cast<int>(blockDim.x);
    const int output0 = static_cast<int>(blockIdx.x) * blockOutputSpan + static_cast<int>(threadIdx.x);
    const int output1 = output0 + static_cast<int>(blockDim.x);
    const bool valid0 = output0 < n;
    const bool valid1 = output1 < n;

    if (!valid0 && !valid1) return;

    const float G = 1.0f;
    const float softening = 0.001f;

    Particle p0;
    Particle p1;
    float fx0 = 0.0f;
    float fy0 = 0.0f;
    float fz0 = 0.0f;
    float fx1 = 0.0f;
    float fy1 = 0.0f;
    float fz1 = 0.0f;

    if (valid0) p0 = in[output0];
    if (valid1) p1 = in[output1];

    for (int j = 0; j < n; j++) {
        const float sourceX = in[j].x;
        const float sourceY = in[j].y;
        const float sourceZ = in[j].z;
        const float sourceMass = in[j].mass;

        if (valid0 && output0 != j) {
            const float dx = sourceX - p0.x;
            const float dy = sourceY - p0.y;
            const float dz = sourceZ - p0.z;
            const float distSq = dx * dx + dy * dy + dz * dz + softening;
            const float dist = sqrtf(distSq);
            const float f = (G * p0.mass * sourceMass) / (distSq * dist);

            fx0 += f * dx;
            fy0 += f * dy;
            fz0 += f * dz;
        }

        if (valid1 && output1 != j) {
            const float dx = sourceX - p1.x;
            const float dy = sourceY - p1.y;
            const float dz = sourceZ - p1.z;
            const float distSq = dx * dx + dy * dy + dz * dz + softening;
            const float dist = sqrtf(distSq);
            const float f = (G * p1.mass * sourceMass) / (distSq * dist);

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
        out[output0] = p0;
    }

    if (valid1) {
        p1.vx += (fx1 / p1.mass) * dt;
        p1.vy += (fy1 / p1.mass) * dt;
        p1.vz += (fz1 / p1.mass) * dt;
        p1.x += p1.vx * dt;
        p1.y += p1.vy * dt;
        p1.z += p1.vz * dt;
        out[output1] = p1;
    }
}
