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
        float invDistCubed = invDistSq * invDist;
        float pairForce = targetMass * in[j].mass * invDistCubed;

        fx += pairForce * dx;
        fy += pairForce * dy;
        fz += pairForce * dz;
    }

    float ax = fx / targetMass;
    float ay = fy / targetMass;
    float az = fz / targetMass;

    Particle p = in[i];
    p.vx += ax * dt;
    p.vy += ay * dt;
    p.vz += az * dt;

    p.x += p.vx * dt;
    p.y += p.vy * dt;
    p.z += p.vz * dt;

    out[i] = p;
}
