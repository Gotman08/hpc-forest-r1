// Structure "Array of Structures" (AoS) : intuitive mais naïve sur GPU
// car elle empêche la coalescence parfaite des accès mémoire.
struct Particle {
    float x, y, z;
    float vx, vy, vz;
    float mass;
};

// Kernel CUDA naïf : Simulation gravitationnelle N-Corps (N-Body)
extern "C" __global__ void nbody_step_naive(const Particle* in, Particle* out, int n, float dt) {
    int i = blockIdx.x * blockDim.x + threadIdx.x;
    if (i >= n) return;

    const float G = 1.0f;
    const float softening = 0.001f;
    const float targetX = in[i].x;
    const float targetY = in[i].y;
    const float targetZ = in[i].z;
    const float targetMass = in[i].mass;

    float fx = 0.0f;
    float fy = 0.0f;
    float fz = 0.0f;

    // Each thread scans all source particles; target fields stay in registers.
    for (int j = 0; j < n; j++) {
        if (i == j) continue;

        float dx = in[j].x - targetX;
        float dy = in[j].y - targetY;
        float dz = in[j].z - targetZ;

        float distSq = dx * dx + dy * dy + dz * dz + softening;
        float invDist = rsqrtf(distSq);
        float invDist3 = (invDist * invDist) * invDist;
        float f = (G * targetMass * in[j].mass) * invDist3;

        fx += f * dx;
        fy += f * dy;
        fz += f * dz;
    }

    // Intégration d'Euler explicite
    Particle p = in[i];
    p.vx += (fx / p.mass) * dt;
    p.vy += (fy / p.mass) * dt;
    p.vz += (fz / p.mass) * dt;

    p.x += p.vx * dt;
    p.y += p.vy * dt;
    p.z += p.vz * dt;

    out[i] = p;
}
