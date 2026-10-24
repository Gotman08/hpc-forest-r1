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

    for (int j = 0; j < n; j++) {
        if (i == j) continue;

        float dx = in[j].x - in[i].x;
        float dy = in[j].y - in[i].y;
        float dz = in[j].z - in[i].z;

        float distSq = dx * dx + dy * dy + dz * dz + softening;

        float invDist = rsqrtf(distSq);
        float invDistSq = invDist * invDist;
        invDist *= 1.5f - (0.5f * distSq) * invDistSq;
        invDistSq = invDist * invDist;
        invDist *= 1.5f - (0.5f * distSq) * invDistSq;
        float invDistCube = (invDist * invDist) * invDist;

        float f = ((G * in[i].mass) * in[j].mass) * invDistCube;

        fx += f * dx;
        fy += f * dy;
        fz += f * dz;
    }

    // Conserver l'ordre de l'accumulation de force et de la division par la masse cible.
    Particle p = in[i];
    p.vx += (fx / p.mass) * dt;
    p.vy += (fy / p.mass) * dt;
    p.vz += (fz / p.mass) * dt;

    p.x += p.vx * dt;
    p.y += p.vy * dt;
    p.z += p.vz * dt;

    out[i] = p;
}
