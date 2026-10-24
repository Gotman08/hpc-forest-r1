struct Particle {
    float x, y, z;
    float vx, vy, vz;
    float mass;
};

extern "C" __global__ void nbody_step_naive(const Particle* in, Particle* out, int n, float dt) {
    constexpr int warpWidth = 32;
    const unsigned int warpMask = 0xffffffffu;

    // Each lane handles two targets, so the launch covers 512 targets per block.
    const long long globalIndex0 =
        static_cast<long long>(blockIdx.x) * static_cast<long long>(blockDim.x) * 2LL +
        static_cast<long long>(threadIdx.x);
    const long long globalIndex1 = globalIndex0 + static_cast<long long>(blockDim.x);
    const bool target0Valid = globalIndex0 < static_cast<long long>(n);
    const bool target1Valid = globalIndex1 < static_cast<long long>(n);
    const int i0 = target0Valid ? static_cast<int>(globalIndex0) : 0;
    const int i1 = target1Valid ? static_cast<int>(globalIndex1) : 0;

    Particle p0;
    Particle p1;
    if (target0Valid) {
        p0 = in[i0];
    }
    if (target1Valid) {
        p1 = in[i1];
    }

    const float G = 1.0f;
    const float softening = 0.001f;
    float fx0 = 0.0f;
    float fy0 = 0.0f;
    float fz0 = 0.0f;
    float fx1 = 0.0f;
    float fy1 = 0.0f;
    float fz1 = 0.0f;

    const int lane = static_cast<int>(threadIdx.x) & (warpWidth - 1);

    // Even lanes without valid targets participate in every shuffle.
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

            if (target0Valid && i0 != j) {
                const float dx = xj - p0.x;
                const float dy = yj - p0.y;
                const float dz = zj - p0.z;

                const float distSq = dx * dx + dy * dy + dz * dz + softening;
                const float dist = sqrtf(distSq);
                const float f = (G * p0.mass * massJ) / (distSq * dist);

                fx0 += f * dx;
                fy0 += f * dy;
                fz0 += f * dz;
            }

            if (target1Valid && i1 != j) {
                const float dx = xj - p1.x;
                const float dy = yj - p1.y;
                const float dz = zj - p1.z;

                const float distSq = dx * dx + dy * dy + dz * dz + softening;
                const float dist = sqrtf(distSq);
                const float f = (G * p1.mass * massJ) / (distSq * dist);

                fx1 += f * dx;
                fy1 += f * dy;
                fz1 += f * dz;
            }
        }
    }

    if (target0Valid) {
        p0.vx += (fx0 / p0.mass) * dt;
        p0.vy += (fy0 / p0.mass) * dt;
        p0.vz += (fz0 / p0.mass) * dt;

        p0.x += p0.vx * dt;
        p0.y += p0.vy * dt;
        p0.z += p0.vz * dt;

        out[i0] = p0;
    }

    if (target1Valid) {
        p1.vx += (fx1 / p1.mass) * dt;
        p1.vy += (fy1 / p1.mass) * dt;
        p1.vz += (fz1 / p1.mass) * dt;

        p1.x += p1.vx * dt;
        p1.y += p1.vy * dt;
        p1.z += p1.vz * dt;

        out[i1] = p1;
    }
}
