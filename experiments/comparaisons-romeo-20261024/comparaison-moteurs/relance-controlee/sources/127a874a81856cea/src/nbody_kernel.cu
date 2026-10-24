struct Particle {
    float x, y, z;
    float vx, vy, vz;
    float mass;
};

extern "C" __global__ void nbody_step_naive(const Particle* in, Particle* out, int n, float dt) {
    const int i = blockIdx.x * blockDim.x + threadIdx.x;
    if (i >= n) return;

    const Particle initial = in[i];
    float fx = 0.0f;
    float fy = 0.0f;
    float fz = 0.0f;

    for (int j = 0; j < n; ++j) {
        if (i == j) continue;

        const float dx = in[j].x - initial.x;
        const float dy = in[j].y - initial.y;
        const float dz = in[j].z - initial.z;
        const float distSq = dx * dx + dy * dy + dz * dz + 0.001f;
        float invDist = rsqrtf(distSq);
        const float correction = fmaf(-0.5f * distSq, invDist * invDist, 1.5f);
        invDist *= correction;
        const float invDist3 = (invDist * invDist) * invDist;
        const float forceScale = (initial.mass * in[j].mass) * invDist3;

        fx += forceScale * dx;
        fy += forceScale * dy;
        fz += forceScale * dz;
    }

    Particle result = initial;
    result.vx += (fx / result.mass) * dt;
    result.vy += (fy / result.mass) * dt;
    result.vz += (fz / result.mass) * dt;
    result.x += result.vx * dt;
    result.y += result.vy * dt;
    result.z += result.vz * dt;

    out[i] = result;
}
