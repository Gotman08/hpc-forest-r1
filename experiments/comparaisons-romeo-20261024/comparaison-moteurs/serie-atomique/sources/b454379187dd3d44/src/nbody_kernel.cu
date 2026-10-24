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

    const float softening = 0.001f;

    // Accumulation directe de l'accélération : la masse de la particule
    // cible s'annule avec la division finale de l'accélération par cette masse.
    float ax = 0.0f;
    float ay = 0.0f;
    float az = 0.0f;

    // Approche naïve : chaque thread parcourt toutes les particules en mémoire globale
    // sans utiliser de mémoire partagée (__shared__) ni mettre in[i] en registre.
    for (int j = 0; j < n; j++) {
        if (i == j) continue; // Divergence de branche inutile dans la boucle

        float dx = in[j].x - in[i].x;
        float dy = in[j].y - in[i].y;
        float dz = in[j].z - in[i].z;

        float distSq = dx * dx + dy * dy + dz * dz + softening;
        // Variante de précision pour isoler le coût et l'effet de rsqrtf.
        float invDist = 1.0f / sqrtf(distSq);

        // Factorise r^-3 avec la masse source. Ces deux produits sont indépendants
        // après invDist, ce qui peut raccourcir la chaîne de dépendances.
        float invDistSq = invDist * invDist;
        float massInvDist = in[j].mass * invDist;
        float a = massInvDist * invDistSq;

        ax += a * dx;
        ay += a * dy;
        az += a * dz;
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
