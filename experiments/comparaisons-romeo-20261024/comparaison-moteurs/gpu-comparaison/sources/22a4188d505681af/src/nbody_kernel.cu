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
    const Particle target = in[i];

    float fx = 0.0f;
    float fy = 0.0f;
    float fz = 0.0f;

    // Retain target-mass multiplication and final division to preserve their
    // float32 behavior for very small or large positive target masses.
    for (int j = 0; j < n; j++) {
        if (i == j) continue;

        float dx = in[j].x - target.x;
        float dy = in[j].y - target.y;
        float dz = in[j].z - target.z;

        float distSq = dx * dx + dy * dy + dz * dz + softening;
        float invDist = rsqrtf(distSq);
        float invDistSq = invDist * invDist;
        float correction = fmaf(-0.5f * distSq, invDistSq, 1.5f);
        // Avoid turning rsqrtf(infinity) == 0 into NaN during refinement.
        if (invDist != 0.0f) {
            invDist *= correction;
        }
        float invDist3 = (invDist * invDist) * invDist;
        float forceScale = ((G * target.mass) * in[j].mass) * invDist3;

        fx += forceScale * dx;
        fy += forceScale * dy;
        fz += forceScale * dz;
    }

    fx /= target.mass;
    fy /= target.mass;
    fz /= target.mass;

    // Intégration d'Euler explicite
    Particle p = target;
    p.vx += fx * dt;
    p.vy += fy * dt;
    p.vz += fz * dt;

    p.x += p.vx * dt;
    p.y += p.vy * dt;
    p.z += p.vz * dt;

    out[i] = p;
}
