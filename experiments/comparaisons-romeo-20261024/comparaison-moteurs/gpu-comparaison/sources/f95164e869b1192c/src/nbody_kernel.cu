struct Particle {
    float x, y, z;
    float vx, vy, vz;
    float mass;
};

extern "C" __global__ void nbody_step_naive(const Particle* in, Particle* out, int n, float dt) {
    int i = blockIdx.x * blockDim.x + threadIdx.x;
    if (i >= n) return;

    const float G = 1.0f;
    const float softening = 0.001f;

    float fx = 0.0f;
    float fy = 0.0f;
    float fz = 0.0f;

    // Skip the self interaction by traversing the two ranges around i.
    #pragma unroll 4
    for (int j = 0; j < i; ++j) {
        float dx = in[j].x - in[i].x;
        float dy = in[j].y - in[i].y;
        float dz = in[j].z - in[i].z;

        float distSq = dx * dx + dy * dy + dz * dz + softening;
        float inverseDistance = rsqrtf(distSq);
        float f = (G * in[i].mass * in[j].mass) * inverseDistance * inverseDistance * inverseDistance;

        fx += f * dx;
        fy += f * dy;
        fz += f * dz;
    }

    #pragma unroll 4
    for (int j = i + 1; j < n; ++j) {
        float dx = in[j].x - in[i].x;
        float dy = in[j].y - in[i].y;
        float dz = in[j].z - in[i].z;

        float distSq = dx * dx + dy * dy + dz * dz + softening;
        float inverseDistance = rsqrtf(distSq);
        float f = (G * in[i].mass * in[j].mass) * inverseDistance * inverseDistance * inverseDistance;

        fx += f * dx;
        fy += f * dy;
        fz += f * dz;
    }

    Particle p = in[i];
    p.vx += (fx / p.mass) * dt;
    p.vy += (fy / p.mass) * dt;
    p.vz += (fz / p.mass) * dt;

    p.x += p.vx * dt;
    p.y += p.vy * dt;
    p.z += p.vz * dt;

    out[i] = p;
}
