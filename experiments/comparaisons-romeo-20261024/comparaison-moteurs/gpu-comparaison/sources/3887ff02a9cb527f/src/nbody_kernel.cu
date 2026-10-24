struct Particle {
    float x, y, z;
    float vx, vy, vz;
    float mass;
};

__device__ __forceinline__ float inverseDistanceCubed(float distSq) {
    float invDist = rsqrtf(distSq);
    const float halfDistSq = 0.5f * distSq;
    invDist *= 1.5f - halfDistSq * invDist * invDist;
    return invDist * invDist * invDist;
}

extern "C" __global__ void nbody_step_naive(const Particle* in, Particle* out, int n, float dt) {
    constexpr int warpWidth = 32;
    const unsigned int warpMask = 0xffffffffu;
    const long long particleCount = static_cast<long long>(n);

    const long long globalIndex =
        static_cast<long long>(blockIdx.x) * static_cast<long long>(blockDim.x) +
        static_cast<long long>(threadIdx.x);
    const bool targetValid = globalIndex < particleCount;
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
    const long long fullTileLimit = (particleCount / warpWidth) * warpWidth;

    // Full tiles need no per-source bounds checks. Every lane still participates
    // in all shuffles, including lanes whose target index is outside n.
    for (long long tileBase = 0; tileBase < fullTileLimit; tileBase += warpWidth) {
        const long long sourceIndex = tileBase + lane;
        const Particle& source = in[static_cast<int>(sourceIndex)];
        const float sourceX = source.x;
        const float sourceY = source.y;
        const float sourceZ = source.z;
        const float sourceMass = source.mass;

        #pragma unroll
        for (int sourceLane = 0; sourceLane < warpWidth; ++sourceLane) {
            const long long sourceJ = tileBase + sourceLane;
            const float xj = __shfl_sync(warpMask, sourceX, sourceLane);
            const float yj = __shfl_sync(warpMask, sourceY, sourceLane);
            const float zj = __shfl_sync(warpMask, sourceZ, sourceLane);
            const float massJ = __shfl_sync(warpMask, sourceMass, sourceLane);

            if (targetValid && i != sourceJ) {
                const float dx = xj - p.x;
                const float dy = yj - p.y;
                const float dz = zj - p.z;
                const float distSq = dx * dx + dy * dy + dz * dz + softening;
                const float f = (G * p.mass * massJ) * inverseDistanceCubed(distSq);

                fx += f * dx;
                fy += f * dy;
                fz += f * dz;
            }
        }
    }

    // The final partial tile has a uniform trip count for every lane in the warp.
    const long long tailBase = fullTileLimit;
    if (tailBase < particleCount) {
        const long long sourceIndex = tailBase + lane;
        float sourceX = 0.0f;
        float sourceY = 0.0f;
        float sourceZ = 0.0f;
        float sourceMass = 0.0f;

        if (sourceIndex < particleCount) {
            const Particle& source = in[static_cast<int>(sourceIndex)];
            sourceX = source.x;
            sourceY = source.y;
            sourceZ = source.z;
            sourceMass = source.mass;
        }

        const int tailCount = static_cast<int>(particleCount - tailBase);
        for (int sourceLane = 0; sourceLane < tailCount; ++sourceLane) {
            const long long sourceJ = tailBase + sourceLane;
            const float xj = __shfl_sync(warpMask, sourceX, sourceLane);
            const float yj = __shfl_sync(warpMask, sourceY, sourceLane);
            const float zj = __shfl_sync(warpMask, sourceZ, sourceLane);
            const float massJ = __shfl_sync(warpMask, sourceMass, sourceLane);

            if (targetValid && i != sourceJ) {
                const float dx = xj - p.x;
                const float dy = yj - p.y;
                const float dz = zj - p.z;
                const float distSq = dx * dx + dy * dy + dz * dz + softening;
                const float f = (G * p.mass * massJ) * inverseDistanceCubed(distSq);

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
