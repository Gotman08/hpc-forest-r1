struct Particle {
    float x, y, z;
    float vx, vy, vz;
    float mass;
};

extern "C" __global__ void nbody_step_naive(const Particle* in, Particle* out, int n, float dt) {
    constexpr int warpWidth = 32;
    const unsigned int warpMask = 0xffffffffu;

    const long long globalIndex =
        static_cast<long long>(blockIdx.x) * static_cast<long long>(blockDim.x) +
        static_cast<long long>(threadIdx.x);
    const bool targetValid = globalIndex < static_cast<long long>(n);
    const int i = targetValid ? static_cast<int>(globalIndex) : 0;

    Particle p;
    if (targetValid) {
        p = in[i];
    }

    const float G = 1.0f;
    const float softening = 0.001f;
    float fx = 0.0f;
    float fy = 0.0f;
    float fz = 0.0f;

    const int lane = static_cast<int>(threadIdx.x) & (warpWidth - 1);

    // All lanes, including lanes without a valid destination, participate in each shuffle.
    for (long long tileBase = 0; tileBase < static_cast<long long>(n); tileBase += warpWidth) {
        const long long sourceIndex = tileBase + lane;
        float sourceX = 0.0f;
        float sourceY = 0.0f;
        float sourceZ = 0.0f;
        float sourceMass = 0.0f;

        if (sourceIndex < static_cast<long long>(n)) {
            const Particle& source = in[static_cast<int>(sourceIndex)];
            sourceX = source.x;
            sourceY = source.y;
            sourceZ = source.z;
            sourceMass = source.mass;
        }

        #pragma unroll
        for (int sourceLane = 0; sourceLane < warpWidth; ++sourceLane) {
            const long long sourceJ = tileBase + sourceLane;
            if (sourceJ >= static_cast<long long>(n)) {
                break;
            }

            const float xj = __shfl_sync(warpMask, sourceX, sourceLane);
            const float yj = __shfl_sync(warpMask, sourceY, sourceLane);
            const float zj = __shfl_sync(warpMask, sourceZ, sourceLane);
            const float massJ = __shfl_sync(warpMask, sourceMass, sourceLane);
            const int j = static_cast<int>(sourceJ);

            if (targetValid && i != j) {
                const float dx = xj - p.x;
                const float dy = yj - p.y;
                const float dz = zj - p.z;

                const float distSq = dx * dx + dy * dy + dz * dz + softening;
                const float dist = sqrtf(distSq);
                const float f = (G * p.mass * massJ) / (distSq * dist);

                fx += f * dx;
                fy += f * dy;
                fz += f * dz;
            }
        }
    }

    if (targetValid) {
        p.vx += (fx / p.mass) * dt;
        p.vy += (fy / p.mass) * dt;
        p.vz += (fz / p.mass) * dt;

        p.x += p.vx * dt;
        p.y += p.vy * dt;
        p.z += p.vz * dt;

        out[i] = p;
    }
}
