// Structure "Array of Structures" : intuitive but not ideal for GPU memory coalescing.
struct Particle {
    float x, y, z;
    float vx, vy, vz;
    float mass;
};

// Naive CUDA N-body step: one output particle per thread.
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
        float invDist3 = invDistSq * invDist;

        // Correct the inverse-distance cube directly from q = distSq * invDist^2.
        // The first-order factor 1 - 1.5 * (q - 1) leaves a second-order residual.
        // Skip refinement for infinity: rsqrtf(infinity) is zero, and infinity * zero is NaN.
        if (invDist != 0.0f) {
            float squareError = fmaf(distSq, invDistSq, -1.0f);
            float cubeCorrection = fmaf(-1.5f, squareError, 1.0f);
            invDist3 *= cubeCorrection;
        }

        float f = (G * in[i].mass * in[j].mass) * invDist3;

        fx += f * dx;
        fy += f * dy;
        fz += f * dz;
    }

    // Explicit Euler integration; preserve the original target-mass division.
    Particle p = in[i];
    p.vx += (fx / p.mass) * dt;
    p.vy += (fy / p.mass) * dt;
    p.vz += (fz / p.mass) * dt;

    p.x += p.vx * dt;
    p.y += p.vy * dt;
    p.z += p.vz * dt;

    out[i] = p;
}
