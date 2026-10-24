struct Particle {
    float x, y, z;
    float vx, vy, vz;
    float mass;
};

// The launch uses 256 threads and 256 target items per block.
// Each source tile is loaded once per CTA and reused by its target threads.
extern "C" __global__ void nbody_step_naive(const Particle* in, Particle* out, int n, float dt) {
    const int tid = threadIdx.x;
    const int i = blockIdx.x * blockDim.x + tid;
    const bool active = i < n;

    Particle target{};
    if (active) {
        target = in[i];
    }

    __shared__ float tileX[256];
    __shared__ float tileY[256];
    __shared__ float tileZ[256];
    __shared__ float tileMass[256];

    const float G = 1.0f;
    const float softening = 0.001f;
    float fx = 0.0f;
    float fy = 0.0f;
    float fz = 0.0f;

    for (int tileStart = 0; tileStart < n; tileStart += 256) {
        const int sourceIndex = tileStart + tid;
        if (sourceIndex < n) {
            const Particle source = in[sourceIndex];
            tileX[tid] = source.x;
            tileY[tid] = source.y;
            tileZ[tid] = source.z;
            tileMass[tid] = source.mass;
        } else {
            tileX[tid] = 0.0f;
            tileY[tid] = 0.0f;
            tileZ[tid] = 0.0f;
            tileMass[tid] = 0.0f;
        }
        __syncthreads();

        if (active) {
            int tileCount = n - tileStart;
            if (tileCount > 256) {
                tileCount = 256;
            }
            for (int k = 0; k < tileCount; ++k) {
                const int j = tileStart + k;
                if (i == j) {
                    continue;
                }

                const float dx = tileX[k] - target.x;
                const float dy = tileY[k] - target.y;
                const float dz = tileZ[k] - target.z;
                const float distSq = dx * dx + dy * dy + dz * dz + softening;
                const float dist = sqrtf(distSq);
                const float f = (G * target.mass * tileMass[k]) / (distSq * dist);
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
