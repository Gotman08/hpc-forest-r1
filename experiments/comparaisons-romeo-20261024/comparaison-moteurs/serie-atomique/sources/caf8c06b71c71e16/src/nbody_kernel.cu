struct Particle {
    float x, y, z;
    float vx, vy, vz;
    float mass;
};

extern "C" __global__ void nbody_step_naive(const Particle* in, Particle* out, int n, float dt) {
    int i = blockIdx.x * blockDim.x + threadIdx.x;
    if (i >= n) return;

    const float softening = 0.001f;
    Particle p = in[i];

    float ax = 0.0f;
    float ay = 0.0f;
    float az = 0.0f;

    for (int j = 0; j < i; ++j) {
        float dx = in[j].x - p.x;
        float dy = in[j].y - p.y;
        float dz = in[j].z - p.z;

        float distSq = dx * dx + dy * dy + dz * dz + softening;
        float invDist = rsqrtf(distSq);
        float invDist3 = invDist * invDist * invDist;
        float scale = in[j].mass * invDist3;

        ax += scale * dx;
        ay += scale * dy;
        az += scale * dz;
    }

    for (int j = i + 1; j < n; ++j) {
        float dx = in[j].x - p.x;
        float dy = in[j].y - p.y;
        float dz = in[j].z - p.z;

        float distSq = dx * dx + dy * dy + dz * dz + softening;
        float invDist = rsqrtf(distSq);
        float invDist3 = invDist * invDist * invDist;
        float scale = in[j].mass * invDist3;

        ax += scale * dx;
        ay += scale * dy;
        az += scale * dz;
    }

    // For ordinary finite masses, the target mass cancels from force / mass.
    // Keep the identity factor so zero and non-finite target masses remain non-finite.
    float massIdentity = p.mass / p.mass;
    p.vx += (ax * massIdentity) * dt;
    p.vy += (ay * massIdentity) * dt;
    p.vz += (az * massIdentity) * dt;

    p.x += p.vx * dt;
    p.y += p.vy * dt;
    p.z += p.vz * dt;

    out[i] = p;
}
