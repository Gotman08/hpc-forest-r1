// Structure "Array of Structures" (AoS), preserved in global memory.
struct Particle {
    float x, y, z;
    float vx, vy, vz;
    float mass;
};

// One output particle per active thread; source particles are staged by block.
extern "C" __global__ void nbody_step_naive(const Particle* in, Particle* out, int n, float dt) {
    const int i = blockIdx.x * blockDim.x + threadIdx.x;
    const bool active = i < n;

    Particle target;
    if (active) target = in[i];

    const float G = 1.0f;
    const float softening = 0.001f;
    float fx = 0.0f;
    float fy = 0.0f;
    float fz = 0.0f;

    extern __shared__ Particle sourceTile[];

    for (int base = 0; base < n; base += blockDim.x) {
        const int sourceIndex = base + threadIdx.x;
        if (sourceIndex < n) sourceTile[threadIdx.x] = in[sourceIndex];
        __syncthreads();

        int tileCount = n - base;
        if (tileCount > blockDim.x) tileCount = blockDim.x;

        if (active) {
            for (int k = 0; k < tileCount; ++k) {
                const int j = base + k;
                if (i == j) continue;

                const Particle source = sourceTile[k];
                const float dx = source.x - target.x;
                const float dy = source.y - target.y;
                const float dz = source.z - target.z;

                const float distSq = dx * dx + dy * dy + dz * dz + softening;
                const float dist = sqrtf(distSq);
                const float f = (G * target.mass * source.mass) / (distSq * dist);

                fx += f * dx;
                fy += f * dy;
                fz += f * dz;
            }
        }
        __syncthreads();
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
