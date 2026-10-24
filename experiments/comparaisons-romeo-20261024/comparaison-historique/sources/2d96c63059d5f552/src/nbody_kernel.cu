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

    float fx = 0.0f;
    float fy = 0.0f;
    float fz = 0.0f;

    // Chaque thread parcourt toutes les particules en mémoire globale.
    for (int j = 0; j < n; j++) {
        if (i == j) continue; // Exclure l'auto-interaction.

        float dx = in[j].x - in[i].x;
        float dy = in[j].y - in[i].y;
        float dz = in[j].z - in[i].z;

        // Accumulation float32 fusionnée de la distance au carré.
        float distSq = fmaf(dx, dx, softening);
        distSq = fmaf(dy, dy, distSq);
        distSq = fmaf(dz, dz, distSq);

        // Former distSq^(-3/2) avec le réciproque de la racine carrée.
        float invDist = rsqrtf(distSq);
        float invDistSq = invDist * invDist;
        float invDistCube = invDistSq * invDist;
        float f = (G * in[i].mass * in[j].mass) * invDistCube;

        fx += f * dx;
        fy += f * dy;
        fz += f * dz;
    }

    // Intégration d'Euler explicite
    Particle p = in[i];
    const float invMass = 1.0f / p.mass;
    p.vx += (fx * invMass) * dt;
    p.vy += (fy * invMass) * dt;
    p.vz += (fz * invMass) * dt;

    p.x += p.vx * dt;
    p.y += p.vy * dt;
    p.z += p.vz * dt;

    out[i] = p;
}
