// Structure Array of Structures used by the original one-thread-per-target kernel.
struct Particle {
    float x, y, z;
    float vx, vy, vz;
    float mass;
};

enum { kSourceTileCapacity = 256 };

// CUDA N-body simulation using CTA-level shared-memory source tiles.
extern "C" __global__ void nbody_step_naive(const Particle* in, Particle* out, int n, float dt) {
    __shared__ float sourceX[kSourceTileCapacity];
    __shared__ float sourceY[kSourceTileCapacity];
    __shared__ float sourceZ[kSourceTileCapacity];
    __shared__ float sourceMass[kSourceTileCapacity];

    int i = blockIdx.x * blockDim.x + threadIdx.x;
    bool active = i < n;

    Particle target;
    if (active) {
        target = in[i];
    }

    const float G = 1.0f;
    const float softening = 0.001f;

    float fx = 0.0f;
    float fy = 0.0f;
    float fz = 0.0f;

    int tileBase = 0;
    while (tileBase < n) {
        int remaining = n - tileBase;
        int tileCount = remaining < kSourceTileCapacity ? remaining : kSourceTileCapacity;

        // Cooperatively load the source tile. Partial tiles only load valid sources.
        for (int k = (int)threadIdx.x; k < tileCount; k += (int)blockDim.x) {
            int j = tileBase + k;
            sourceX[k] = in[j].x;
            sourceY[k] = in[j].y;
            sourceZ[k] = in[j].z;
            sourceMass[k] = in[j].mass;
        }
        __syncthreads();

        // Inactive target lanes still reach both barriers in every tile iteration.
        if (active) {
            for (int k = 0; k < tileCount; k++) {
                int j = tileBase + k;
                if (i == j) continue;

                float dx = sourceX[k] - target.x;
                float dy = sourceY[k] - target.y;
                float dz = sourceZ[k] - target.z;

                float distSq = dx * dx + dy * dy + dz * dz + softening;
                float dist = sqrtf(distSq);

                float f = (G * target.mass * sourceMass[k]) / (distSq * dist);

                fx += f * dx;
                fy += f * dy;
                fz += f * dz;
            }
        }
        __syncthreads();

        tileBase += tileCount;
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
