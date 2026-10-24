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

    // Accumulate acceleration directly; the target mass cancels from force / mass.
    float ax = 0.0f;
    float ay = 0.0f;
    float az = 0.0f;

    for (int j = 0; j < n; j++) {
        // Keep self-interaction excluded before evaluating the distance scale.
        if (i == j) continue;

        float dx = in[j].x - in[i].x;
        float dy = in[j].y - in[i].y;
        float dz = in[j].z - in[i].z;

        float distSq = dx * dx + dy * dy + dz * dz + softening;
        float invDist = rsqrtf(distSq);

        // One Newton refinement improves rsqrtf accuracy. Skip it when the
        // reciprocal is zero (for example, if distSq overflowed to infinity).
        if (invDist != 0.0f) {
            float scaledInvDist = distSq * invDist;
            invDist *= 1.5f - 0.5f * scaledInvDist * invDist;
        }

        float accelerationScale = G * in[j].mass * invDist * invDist * invDist;

        ax += accelerationScale * dx;
        ay += accelerationScale * dy;
        az += accelerationScale * dz;
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
