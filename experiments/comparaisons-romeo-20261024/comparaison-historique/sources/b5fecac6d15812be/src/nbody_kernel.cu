struct Particle {
    float x, y, z;
    float vx, vy, vz;
    float mass;
};

extern "C" __global__ void nbody_step_naive(const Particle* in, Particle* out, int n, float dt) {
    const int lane = threadIdx.x & 31;
    const int warpInBlock = threadIdx.x >> 5;
    const int targetSlot = warpInBlock / 3;
    const int warpInTarget = warpInBlock - targetSlot * 3;
    const int i = static_cast<int>(blockIdx.x) * 2 + targetSlot;
    const bool validTarget = i < n;

    const float G = 1.0f;
    const float softening = 0.001f;

    __shared__ float partial_fx[2][3];
    __shared__ float partial_fy[2][3];
    __shared__ float partial_fz[2][3];

    float fx = 0.0f;
    float fy = 0.0f;
    float fz = 0.0f;

    if (validTarget) {
        const Particle target = in[i];
        int j = warpInTarget * 32 + lane;
        while (j < n) {
            if (j != i) {
                const float dx = in[j].x - target.x;
                const float dy = in[j].y - target.y;
                const float dz = in[j].z - target.z;

                const float distSq = dx * dx + dy * dy + dz * dz + softening;
                const float dist = sqrtf(distSq);
                const float f = (G * target.mass * in[j].mass) / (distSq * dist);

                fx += f * dx;
                fy += f * dy;
                fz += f * dz;
            }
            if (n - j <= 96) break;
            j += 96;
        }
    }

    for (int offset = 16; offset > 0; offset >>= 1) {
        fx += __shfl_down_sync(0xffffffffu, fx, offset);
        fy += __shfl_down_sync(0xffffffffu, fy, offset);
        fz += __shfl_down_sync(0xffffffffu, fz, offset);
    }

    if (lane == 0) {
        partial_fx[targetSlot][warpInTarget] = fx;
        partial_fy[targetSlot][warpInTarget] = fy;
        partial_fz[targetSlot][warpInTarget] = fz;
    }
    __syncthreads();

    if (validTarget && warpInTarget == 0 && lane == 0) {
        Particle p = in[i];
        const float total_fx = partial_fx[targetSlot][0] + partial_fx[targetSlot][1] + partial_fx[targetSlot][2];
        const float total_fy = partial_fy[targetSlot][0] + partial_fy[targetSlot][1] + partial_fy[targetSlot][2];
        const float total_fz = partial_fz[targetSlot][0] + partial_fz[targetSlot][1] + partial_fz[targetSlot][2];

        p.vx += (total_fx / p.mass) * dt;
        p.vy += (total_fy / p.mass) * dt;
        p.vz += (total_fz / p.mass) * dt;

        p.x += p.vx * dt;
        p.y += p.vy * dt;
        p.z += p.vz * dt;

        out[i] = p;
    }
}
