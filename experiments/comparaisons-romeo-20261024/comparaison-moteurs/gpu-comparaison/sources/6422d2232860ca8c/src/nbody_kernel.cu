// Structure "Array of Structures" (AoS) : intuitive mais naïve sur GPU
// car elle empêche la coalescence parfaite des accès mémoire.
struct Particle {
    float x, y, z;
    float vx, vy, vz;
    float mass;
};

// Chaque thread calcule une cible; le CTA partage les données des sources.
extern "C" __global__ void nbody_step_naive(const Particle* in, Particle* out, int n, float dt) {
    enum { SOURCE_TILE_SIZE = 512 };
    __shared__ float sourceX[SOURCE_TILE_SIZE];
    __shared__ float sourceY[SOURCE_TILE_SIZE];
    __shared__ float sourceZ[SOURCE_TILE_SIZE];
    __shared__ float sourceMass[SOURCE_TILE_SIZE];

    const int i = blockIdx.x * blockDim.x + threadIdx.x;
    const bool validTarget = i < n;

    const float G = 1.0f;
    const float softening = 0.001f;

    float targetX = 0.0f;
    float targetY = 0.0f;
    float targetZ = 0.0f;
    float targetMass = 0.0f;
    if (validTarget) {
        targetX = in[i].x;
        targetY = in[i].y;
        targetZ = in[i].z;
        targetMass = in[i].mass;
    }

    float fx = 0.0f;
    float fy = 0.0f;
    float fz = 0.0f;

    for (int tileBase = 0; tileBase < n; tileBase += SOURCE_TILE_SIZE) {
        for (int offset = threadIdx.x; offset < SOURCE_TILE_SIZE; offset += blockDim.x) {
            const int j = tileBase + offset;
            if (j < n) {
                sourceX[offset] = in[j].x;
                sourceY[offset] = in[j].y;
                sourceZ[offset] = in[j].z;
                sourceMass[offset] = in[j].mass;
            }
        }
        __syncthreads();

        if (validTarget) {
            int tileCount = n - tileBase;
            if (tileCount > SOURCE_TILE_SIZE) {
                tileCount = SOURCE_TILE_SIZE;
            }
            for (int offset = 0; offset < tileCount; ++offset) {
                const int j = tileBase + offset;
                if (i == j) continue;

                float dx = sourceX[offset] - targetX;
                float dy = sourceY[offset] - targetY;
                float dz = sourceZ[offset] - targetZ;

                float distSq = dx * dx + dy * dy + dz * dz + softening;
                float dist = sqrtf(distSq);

                float f = (G * targetMass * sourceMass[offset]) / (distSq * dist);

                fx += f * dx;
                fy += f * dy;
                fz += f * dz;
            }
        }
        __syncthreads();
    }

    if (validTarget) {
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
