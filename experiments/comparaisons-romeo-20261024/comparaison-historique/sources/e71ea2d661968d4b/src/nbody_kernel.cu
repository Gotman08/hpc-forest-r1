struct Particle {
    float x, y, z;
    float vx, vy, vz;
    float mass;
};

#define SOURCE_TILE_SIZE 448

extern "C" __global__ void nbody_step_naive(const Particle* in, Particle* out, int n, float dt) {
    const int i = blockIdx.x * blockDim.x + threadIdx.x;
    const bool ownsOutput = i < n;

    extern __shared__ Particle stagedSources[];

    Particle target;
    if (ownsOutput) {
        target = in[i];
    }

    const float G = 1.0f;
    const float softening = 0.001f;
    float fx = 0.0f;
    float fy = 0.0f;
    float fz = 0.0f;

    int sourceBase = 0;
    while (sourceBase < n) {
        int tileCount = n - sourceBase;
        if (tileCount > SOURCE_TILE_SIZE) {
            tileCount = SOURCE_TILE_SIZE;
        }

        for (int offset = threadIdx.x; offset < tileCount; offset += blockDim.x) {
            stagedSources[offset] = in[sourceBase + offset];
        }
        __syncthreads();

        if (ownsOutput) {
            for (int offset = 0; offset < tileCount; ++offset) {
                const int j = sourceBase + offset;
                if (i == j) {
                    continue;
                }

                const Particle source = stagedSources[offset];
                float dx = source.x - target.x;
                float dy = source.y - target.y;
                float dz = source.z - target.z;

                float distSq = dx * dx + dy * dy + dz * dz + softening;
                float dist = sqrtf(distSq);
                float f = (G * target.mass * source.mass) / (distSq * dist);

                fx += f * dx;
                fy += f * dy;
                fz += f * dz;
            }
        }
        __syncthreads();

        sourceBase += tileCount;
    }

    if (ownsOutput) {
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
