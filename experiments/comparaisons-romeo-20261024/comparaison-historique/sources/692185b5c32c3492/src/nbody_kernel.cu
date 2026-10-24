struct Particle {
    float x, y, z;
    float vx, vy, vz;
    float mass;
};

extern "C" __global__ void nbody_step_naive(const Particle* in, Particle* out, int n, float dt) {
    int i = blockIdx.x * blockDim.x + threadIdx.x;
    if (i >= n) return;

    const float softening = 0.001f;
    const float targetMass = in[i].mass;

    float ax = 0.0f;
    float ay = 0.0f;
    float az = 0.0f;

    #pragma unroll 2
    for (int j = 0; j < n; j++) {
        if (i == j) continue;

        float dx = in[j].x - in[i].x;
        float dy = in[j].y - in[i].y;
        float dz = in[j].z - in[i].z;

        float distSq = dx * dx + dy * dy + dz * dz + softening;
        float invDist = rsqrtf(distSq);
        float invDist2 = invDist * invDist;
        invDist = invDist * (1.5f - (0.5f * distSq) * invDist2);
        float invDist3 = invDist * invDist * invDist;
        float coefficient = (targetMass * in[j].mass) * invDist3;

        ax += coefficient * dx;
        ay += coefficient * dy;
        az += coefficient * dz;
    }

    Particle p = in[i];
    p.vx += (ax / targetMass) * dt;
    p.vy += (ay / targetMass) * dt;
    p.vz += (az / targetMass) * dt;

    p.x += p.vx * dt;
    p.y += p.vy * dt;
    p.z += p.vz * dt;

    out[i] = p;
}
