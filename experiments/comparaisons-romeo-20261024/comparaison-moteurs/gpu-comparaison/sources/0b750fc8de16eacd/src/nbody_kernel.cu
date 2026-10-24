// Structure "Array of Structures" (AoS) : intuitive mais naïve sur GPU
// car elle empêche la coalescence parfaite des accès mémoire.
struct Particle {
    float x, y, z;
    float vx, vy, vz;
    float mass;
};

// Accumulate one source interaction; callers explicitly unroll groups of four.
#define N_BODY_ACCUMULATE_SOURCE(J) \
    do { \
        const int k = (J); \
        const float dx = in[k].x - in[i].x; \
        const float dy = in[k].y - in[i].y; \
        const float dz = in[k].z - in[i].z; \
        const float distSq = dx * dx + dy * dy + dz * dz + softening; \
        const float dist = sqrtf(distSq); \
        const float f = (G * in[i].mass * in[k].mass) / (distSq * dist); \
        fx += f * dx; \
        fy += f * dy; \
        fz += f * dz; \
    } while (0)

extern "C" __global__ void nbody_step_naive(const Particle* in, Particle* out, int n, float dt) {
    int i = blockIdx.x * blockDim.x + threadIdx.x;
    if (i >= n) return;

    const float G = 1.0f;
    const float softening = 0.001f;

    float fx = 0.0f;
    float fy = 0.0f;
    float fz = 0.0f;

    // Visit [0, i) and (i, n), so the self interaction is never evaluated.
    int j = 0;
    for (; j < i - 3; j += 4) {
        N_BODY_ACCUMULATE_SOURCE(j);
        N_BODY_ACCUMULATE_SOURCE(j + 1);
        N_BODY_ACCUMULATE_SOURCE(j + 2);
        N_BODY_ACCUMULATE_SOURCE(j + 3);
    }
    for (; j < i; ++j) {
        N_BODY_ACCUMULATE_SOURCE(j);
    }

    j = i + 1;
    for (; j < n - 3; j += 4) {
        N_BODY_ACCUMULATE_SOURCE(j);
        N_BODY_ACCUMULATE_SOURCE(j + 1);
        N_BODY_ACCUMULATE_SOURCE(j + 2);
        N_BODY_ACCUMULATE_SOURCE(j + 3);
    }
    for (; j < n; ++j) {
        N_BODY_ACCUMULATE_SOURCE(j);
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

#undef N_BODY_ACCUMULATE_SOURCE
