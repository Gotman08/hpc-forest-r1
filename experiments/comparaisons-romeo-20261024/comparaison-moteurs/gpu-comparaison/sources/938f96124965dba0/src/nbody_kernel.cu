// Each thread computes one target particle; source tiles are shared across the CTA.
struct Particle {
    float x, y, z;
    float vx, vy, vz;
    float mass;
};

extern "C" __global__ void nbody_step_naive(const Particle* in, Particle* out, int n, float dt) {
    constexpr int kSourceTile = 2048;

    extern __shared__ float shared[];
    float* tileX = shared;
    float* tileY = tileX + kSourceTile;
    float* tileZ = tileY + kSourceTile;
    float* tileMass = tileZ + kSourceTile;

    const int i = blockIdx.x * blockDim.x + threadIdx.x;
    const bool active = i < n;
    Particle target;
    if (active) {
        target = in[i];
    }

    const float G = 1.0f;
    const float softening = 0.001f;
    float fx = 0.0f;
    float fy = 0.0f;
    float fz = 0.0f;

    for (int tileStart = 0; tileStart < n;) {
        const int remaining = n - tileStart;
        const int tileCount = remaining < kSourceTile ? remaining : kSourceTile;

        for (int k = threadIdx.x; k < tileCount; k += blockDim.x) {
            const int sourceIndex = tileStart + k;
            tileX[k] = in[sourceIndex].x;
            tileY[k] = in[sourceIndex].y;
            tileZ[k] = in[sourceIndex].z;
            tileMass[k] = in[sourceIndex].mass;
        }
        __syncthreads();

        if (active) {
            for (int k = 0; k < tileCount; ++k) {
                const int j = tileStart + k;
                if (i == j) continue;

                float dx = tileX[k] - target.x;
                float dy = tileY[k] - target.y;
                float dz = tileZ[k] - target.z;

                float distSq = dx * dx + dy * dy + dz * dz + softening;
                float dist = sqrtf(distSq);
                float f = (G * target.mass * tileMass[k]) / (distSq * dist);

                fx += f * dx;
                fy += f * dy;
                fz += f * dz;
            }
        }
        __syncthreads();
        tileStart += tileCount;
    }

    if (active) {
        target.vx += (fx / target.mass) * dt;
        target.vy += (fy / target.mass) * dt;
        target.vz += (fz / target.mass) * dt;

        target.x += target.vx * dt;
        target.y += target.vy * dt;
        target.z += target.vz * dt;

        out[i] = target;
    }
}
