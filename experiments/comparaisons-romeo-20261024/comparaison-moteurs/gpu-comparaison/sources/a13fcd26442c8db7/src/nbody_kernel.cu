struct Particle {
    float x, y, z;
    float vx, vy, vz;
    float mass;
};

struct SourceParticle {
    float x, y, z, mass;
};

extern "C" __global__ void nbody_step_naive(const Particle* in, Particle* out, int n, float dt) {
    extern __shared__ SourceParticle sourceTile[];

    const int tid = threadIdx.x;
    const int i = blockIdx.x * blockDim.x + tid;
    const bool active = i < n;

    Particle p;
    if (active) {
        p = in[i];
    }

    const float G = 1.0f;
    const float softening = 0.001f;
    float fx = 0.0f;
    float fy = 0.0f;
    float fz = 0.0f;

    int tileBase = 0;
    while (tileBase < n) {
        const int remaining = n - tileBase;
        const int tileCount = remaining < blockDim.x ? remaining : blockDim.x;

        if (tid < tileCount) {
            const int sourceIndex = tileBase + tid;
            sourceTile[tid].x = in[sourceIndex].x;
            sourceTile[tid].y = in[sourceIndex].y;
            sourceTile[tid].z = in[sourceIndex].z;
            sourceTile[tid].mass = in[sourceIndex].mass;
        }
        __syncthreads();

        if (active) {
            for (int k = 0; k < tileCount; ++k) {
                const int j = tileBase + k;
                if (i == j) continue;

                const float dx = sourceTile[k].x - p.x;
                const float dy = sourceTile[k].y - p.y;
                const float dz = sourceTile[k].z - p.z;

                const float distSq = dx * dx + dy * dy + dz * dz + softening;
                const float dist = sqrtf(distSq);
                const float f = (G * p.mass * sourceTile[k].mass) / (distSq * dist);

                fx += f * dx;
                fy += f * dy;
                fz += f * dz;
            }
        }
        __syncthreads();

        if (remaining <= blockDim.x) break;
        tileBase += blockDim.x;
    }

    if (!active) return;

    p.vx += (fx / p.mass) * dt;
    p.vy += (fy / p.mass) * dt;
    p.vz += (fz / p.mass) * dt;

    p.x += p.vx * dt;
    p.y += p.vy * dt;
    p.z += p.vz * dt;

    out[i] = p;
}
