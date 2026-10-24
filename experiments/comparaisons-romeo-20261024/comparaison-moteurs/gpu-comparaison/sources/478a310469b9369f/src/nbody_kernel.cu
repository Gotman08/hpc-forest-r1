// Structure "Array of Structures" (AoS).
struct Particle {
    float x, y, z;
    float vx, vy, vz;
    float mass;
};

// Each thread updates one target and skips its self-interaction by splitting
// the source range around i.
extern "C" __global__ void nbody_step_naive(const Particle* in, Particle* out, int n, float dt) {
    int i = blockIdx.x * blockDim.x + threadIdx.x;
    if (i >= n) return;

    const float G = 1.0f;
    const float softening = 0.001f;

    float fx = 0.0f;
    float fy = 0.0f;
    float fz = 0.0f;

    #pragma unroll 8
    for (int j = 0; j < i; j++) {
        float dx = in[j].x - in[i].x;
        float dy = in[j].y - in[i].y;
        float dz = in[j].z - in[i].z;

        float distSq = dx * dx + dy * dy + dz * dz + softening;
        float invDist = rsqrtf(distSq);
        float invDist3 = invDist * invDist * invDist;
        float f = (G * in[i].mass * in[j].mass) * invDist3;

        fx += f * dx;
        fy += f * dy;
        fz += f * dz;
    }

    #pragma unroll 8
    for (int j = i + 1; j < n; j++) {
        float dx = in[j].x - in[i].x;
        float dy = in[j].y - in[i].y;
        float dz = in[j].z - in[i].z;

        float distSq = dx * dx + dy * dy + dz * dz + softening;
        float invDist = rsqrtf(distSq);
        float invDist3 = invDist * invDist * invDist;
        float f = (G * in[i].mass * in[j].mass) * invDist3;

        fx += f * dx;
        fy += f * dy;
        fz += f * dz;
    }

    Particle p = in[i];
    const float minNormalMass = 1.17549435e-38f;
    const float maxReciprocalSafeMass = 8.50705867e37f;
    if ((p.mass >= minNormalMass && p.mass <= maxReciprocalSafeMass) ||
        (p.mass <= -minNormalMass && p.mass >= -maxReciprocalSafeMass)) {
        const float invMass = 1.0f / p.mass;
        p.vx += (fx * invMass) * dt;
        p.vy += (fy * invMass) * dt;
        p.vz += (fz * invMass) * dt;
    } else {
        p.vx += (fx / p.mass) * dt;
        p.vy += (fy / p.mass) * dt;
        p.vz += (fz / p.mass) * dt;
    }

    p.x += p.vx * dt;
    p.y += p.vy * dt;
    p.z += p.vz * dt;

    out[i] = p;
}
