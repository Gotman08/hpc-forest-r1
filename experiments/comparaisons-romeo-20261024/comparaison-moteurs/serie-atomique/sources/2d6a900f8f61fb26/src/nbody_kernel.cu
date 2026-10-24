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

    float ax = 0.0f;
    float ay = 0.0f;
    float az = 0.0f;

    for (int j = 0; j < n; j++) {
        if (i == j) continue;

        float dx = in[j].x - in[i].x;
        float dy = in[j].y - in[i].y;
        float dz = in[j].z - in[i].z;

        float distSq = dx * dx + dy * dy + dz * dz + softening;
        float invDist = rsqrtf(distSq);
        float invDist2 = invDist * invDist;
        float massInvDist = G * in[j].mass * invDist;
        float scale = massInvDist * invDist2;

        ax = fmaf(scale, dx, ax);
        ay = fmaf(scale, dy, ay);
        az = fmaf(scale, dz, az);
    }

    Particle p = in[i];
    p.vx += ax * dt;
    p.vy += ay * dt;
    p.vz += az * dt;

    p.x += p.vx * dt;
    p.y += p.vy * dt;
    p.z += p.vz * dt;

    out[i] = p;
}
