// Structure "Array of Structures" (AoS) used for particle state.
struct Particle {
    float x, y, z;
    float vx, vy, vz;
    float mass;
};

// One thread computes each target; each CTA cooperatively stages source tiles.
extern "C" __global__ void nbody_step_naive(const Particle* in, Particle* out, int n, float dt) {
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

    // Four 1536-element float arrays use 24,576 bytes of shared memory.
    __shared__ float tileX[1536];
    __shared__ float tileY[1536];
    __shared__ float tileZ[1536];
    __shared__ float tileMass[1536];

    for (int base = 0; base < n; ) {
        int tileCount = n - base;
        if (tileCount > 1536) {
            tileCount = 1536;
        }

        for (int k = threadIdx.x; k < tileCount; k += blockDim.x) {
            const int sourceIndex = base + k;
            tileX[k] = in[sourceIndex].x;
            tileY[k] = in[sourceIndex].y;
            tileZ[k] = in[sourceIndex].z;
            tileMass[k] = in[sourceIndex].mass;
        }
        __syncthreads();

        if (active) {
            for (int k = 0; k < tileCount; ++k) {
                const int j = base + k;
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

        // Ensure all consumers finish before the next tile overwrites shared memory.
        __syncthreads();
        base += tileCount;
    }

    if (active) {
        Particle p = target;
        p.vx += (fx / p.mass) * dt;
        p.vy += (fy / p.mass) * dt;
        p.vz += (fz / p.mass) * dt;

        p.x += p.vx * dt;
        p.y += p.vy * dt;
        p.z += p.vz * dt;

        out[i] = p;
    }
}
