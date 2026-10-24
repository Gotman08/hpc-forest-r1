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

    float ax = 0.0f;
    float ay = 0.0f;
    float az = 0.0f;

    // Chaque thread parcourt toutes les particules en mémoire globale.
    for (int j = 0; j < n; j++) {
        if (i == j) continue;

        float dx = in[j].x - in[i].x;
        float dy = in[j].y - in[i].y;
        float dz = in[j].z - in[i].z;

        // Fusions explicites pour sommer les termes de distance au carré.
        float distSq = fmaf(dx, dx, fmaf(dy, dy, fmaf(dz, dz, softening)));
        float invDist = rsqrtf(distSq);
        float invDist2 = invDist * invDist;
        float weightedInvDist = G * in[j].mass * invDist;
        float acceleration = weightedInvDist * invDist2;
        ax += acceleration * dx;
        ay += acceleration * dy;
        az += acceleration * dz;
    }

    // Intégration d'Euler explicite
    Particle p = in[i];
    p.vx += ax * dt;
    p.vy += ay * dt;
    p.vz += az * dt;

    p.x += p.vx * dt;
    p.y += p.vy * dt;
    p.z += p.vz * dt;

    out[i] = p;
}
