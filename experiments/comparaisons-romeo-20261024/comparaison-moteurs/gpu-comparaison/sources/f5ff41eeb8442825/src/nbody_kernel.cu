// Structure "Array of Structures" (AoS).
struct Particle {
    float x, y, z;
    float vx, vy, vz;
    float mass;
};

// CUDA N-Body simulation using a cooperative shared-memory source tile.
extern "C" __global__ void nbody_step_naive(const Particle* in, Particle* out, int n, float dt) {
    const int i = blockIdx.x * blockDim.x + threadIdx.x;
    const int tid = threadIdx.x;

    const float G = 1.0f;
    const float softening = 0.001f;
    const int tileSize = 512;

    __shared__ Particle sourceTile[512];

    float fx = 0.0f;
    float fy = 0.0f;
    float fz = 0.0f;

    // Every thread, including inactive target threads, participates in both barriers.
    for (int tileStart = 0; tileStart < n; tileStart += tileSize) {
        int tileCount = n - tileStart;
        if (tileCount > tileSize) tileCount = tileSize;

        for (int k = tid; k < tileCount; k += blockDim.x) {
            sourceTile[k] = in[tileStart + k];
        }
        __syncthreads();

        if (i < n) {
            for (int k = 0; k < tileCount; ++k) {
                const int j = tileStart + k;
                if (i == j) continue;

                float dx = sourceTile[k].x - in[i].x;
                float dy = sourceTile[k].y - in[i].y;
                float dz = sourceTile[k].z - in[i].z;

                float distSq = dx * dx + dy * dy + dz * dz + softening;
                float dist = sqrtf(distSq);

                float f = (G * in[i].mass * sourceTile[k].mass) / (distSq * dist);

                fx += f * dx;
                fy += f * dy;
                fz += f * dz;
            }
        }
        __syncthreads();
    }

    if (i < n) {
        // Integration of Euler explicit; mass is copied without modification.
        Particle p = in[i];
        p.vx += (fx / p.mass) * dt;
        p.vy += (fy / p.mass) * dt;
        p.vz += (fz / p.mass) * dt;

        p.x += p.vx * dt;
        p.y += p.vy * dt;
        p.z += p.vz * dt;

        out[i] = p;
    }
}
