struct Particle {
    float x, y, z;
    float vx, vy, vz;
    float mass;
};

// One warp computes the force on each output particle.
extern "C" __global__ void nbody_step_naive(const Particle* in, Particle* out, int n, float dt) {
    const int lane = threadIdx.x & 31;
    const int warp = threadIdx.x >> 5;
    const int warps_per_block = blockDim.x >> 5;
    const int i = blockIdx.x * warps_per_block + warp;
    const bool valid = i < n;

    Particle p{};
    if (valid) p = in[i];
    const float targetMass = p.mass;
    const float softening = 0.001f;
    float fx = 0.0f;
    float fy = 0.0f;
    float fz = 0.0f;

    // Each lane accumulates a disjoint, strided subset of the sources.
    #pragma unroll 2
    for (int j = lane; j < n; j += 32) {
        if (valid && j != i) {
            float dx = in[j].x - p.x;
            float dy = in[j].y - p.y;
            float dz = in[j].z - p.z;

            float distSq = dx * dx + dy * dy + dz * dz + softening;
            float invDist = rsqrtf(distSq);
            float invDist2 = invDist * invDist;
            invDist = invDist * (1.5f - (0.5f * distSq) * invDist2);
            float invDist3 = invDist * invDist * invDist;
            float coefficient = (targetMass * in[j].mass) * invDist3;

            fx += coefficient * dx;
            fy += coefficient * dy;
            fz += coefficient * dz;
        }
    }

    // All lanes participate in each warp reduction, including invalid output warps.
    const unsigned mask = 0xffffffffu;
    for (int offset = 16; offset > 0; offset >>= 1) {
        fx += __shfl_down_sync(mask, fx, offset);
        fy += __shfl_down_sync(mask, fy, offset);
        fz += __shfl_down_sync(mask, fz, offset);
    }

    if (lane == 0 && valid) {
        p.vx += (fx / targetMass) * dt;
        p.vy += (fy / targetMass) * dt;
        p.vz += (fz / targetMass) * dt;

        p.x += p.vx * dt;
        p.y += p.vy * dt;
        p.z += p.vz * dt;

        out[i] = p;
    }
}
