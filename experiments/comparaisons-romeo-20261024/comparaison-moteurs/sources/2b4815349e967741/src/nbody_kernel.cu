// Structure "Array of Structures" (AoS) : intuitive mais naïve sur GPU
// car elle empêche la coalescence parfaite des accès mémoire.
struct Particle {
    float x, y, z;
    float vx, vy, vz;
    float mass;
};

// Kernel CUDA naïf : Simulation gravitationnelle N-Corps (N-Body)
extern "C" __global__ void nbody_step_naive(const Particle* in, Particle* out, int n, float dt) {
    const long long stride = (long long)gridDim.x * (long long)blockDim.x;

    for (long long index = (long long)blockIdx.x * (long long)blockDim.x + threadIdx.x;
         index < n;
         index += stride) {
        const int i = (int)index;
        const float G = 1.0f;
        const float softening = 0.001f;

        float fx = 0.0f;
        float fy = 0.0f;
        float fz = 0.0f;

        // Chaque cible parcourt toutes les particules en mémoire globale.
        for (int j = 0; j < n; j++) {
            if (i == j) continue;

            float dx = in[j].x - in[i].x;
            float dy = in[j].y - in[i].y;
            float dz = in[j].z - in[i].z;

            float distSq = dx * dx + dy * dy + dz * dz + softening;
            float dist = sqrtf(distSq);

            float f = (G * in[i].mass * in[j].mass) / (distSq * dist);

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
}
