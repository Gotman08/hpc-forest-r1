// Structure "Array of Structures" (AoS) : intuitive mais naïve sur GPU
// car elle empêche la coalescence parfaite des accès mémoire.
struct Particle {
    float x, y, z;
    float vx, vy, vz;
    float mass;
};

__device__ __forceinline__ void update_target(const Particle* in, Particle* out, int i, int n, float dt) {
    const float G = 1.0f;
    const float softening = 0.001f;
    const Particle target = in[i];

    float fx = 0.0f;
    float fy = 0.0f;
    float fz = 0.0f;

    for (int j = 0; j < n; j++) {
        if (i == j) continue;

        float dx = in[j].x - target.x;
        float dy = in[j].y - target.y;
        float dz = in[j].z - target.z;

        float distSq = dx * dx + dy * dy + dz * dz + softening;
        float dist = sqrtf(distSq);
        float f = (G * target.mass * in[j].mass) / (distSq * dist);

        fx += f * dx;
        fy += f * dy;
        fz += f * dz;
    }

    Particle p = target;
    p.vx += (fx / p.mass) * dt;
    p.vy += (fy / p.mass) * dt;
    p.vz += (fz / p.mass) * dt;

    p.x += p.vx * dt;
    p.y += p.vy * dt;
    p.z += p.vz * dt;

    out[i] = p;
}

// Direct two-target microtile: each thread handles adjacent target pairs.
// Pair assignment uses the actual grid dimensions, so it covers N exactly
// even when the number of launched threads differs from N.
extern "C" __global__ void nbody_step_naive(const Particle* in, Particle* out, int n, float dt) {
    if (n <= 0) return;

    const long long total_threads = (long long)gridDim.x * (long long)blockDim.x;
    if (total_threads <= 0) return;

    const long long thread_index = (long long)blockIdx.x * (long long)blockDim.x + (long long)threadIdx.x;
    const long long pair_stride = 2LL * total_threads;

    for (long long i = 2LL * thread_index; i < (long long)n; i += pair_stride) {
        update_target(in, out, (int)i, n, dt);
        if (i + 1LL < (long long)n) {
            update_target(in, out, (int)(i + 1LL), n, dt);
        }
    }
}
