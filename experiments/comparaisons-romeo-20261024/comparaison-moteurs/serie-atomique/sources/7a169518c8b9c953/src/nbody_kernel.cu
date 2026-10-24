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

    float fx = 0.0f;
    float fy = 0.0f;
    float fz = 0.0f;

    for (int j = 0; j < i; ++j) {
        float dx = in[j].x - p.x;
        float dy = in[j].y - p.y;
        float dz = in[j].z - p.z;

        float distSq = dx * dx + dy * dy + dz * dz + softening;
        float invDist = rsqrtf(distSq);
        if (invDist != 0.0f) {
            float invDistSq = invDist * invDist;
            float correction = fmaf(-0.5f * distSq, invDistSq, 1.5f);
            invDist *= correction;
        }

        float invDist3 = (invDist * invDist) * invDist;
        float forceScale = (p.mass * in[j].mass) * invDist3;
        fx += forceScale * dx;
        fy += forceScale * dy;
        fz += forceScale * dz;
    }

    for (int j = i + 1; j < n; ++j) {
        float dx = in[j].x - p.x;
        float dy = in[j].y - p.y;
        float dz = in[j].z - p.z;

        float distSq = dx * dx + dy * dy + dz * dz + softening;
        float invDist = rsqrtf(distSq);
        if (invDist != 0.0f) {
            float invDistSq = invDist * invDist;
            float correction = fmaf(-0.5f * distSq, invDistSq, 1.5f);
            invDist *= correction;
        }

        float invDist3 = (invDist * invDist) * invDist;
        float forceScale = (p.mass * in[j].mass) * invDist3;
        fx += forceScale * dx;
        fy += forceScale * dy;
        fz += forceScale * dz;
    }

    p.vx += (fx / p.mass) * dt;
    p.vy += (fy / p.mass) * dt;
    p.vz += (fz / p.mass) * dt;

    p.x += p.vx * dt;
    p.y += p.vy * dt;
    p.z += p.vz * dt;

    out[i] = p;
}
