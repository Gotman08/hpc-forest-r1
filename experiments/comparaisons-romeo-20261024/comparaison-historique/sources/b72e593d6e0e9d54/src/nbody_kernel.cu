struct Particle {
    float x, y, z;
    float vx, vy, vz;
    float mass;
};

extern "C" __global__ void nbody_step_naive(const Particle* in, Particle* out, int n, float dt) {
    const int warp_size = 32;
    const int lane = threadIdx.x & (warp_size - 1);
    const int warp_in_block = threadIdx.x / warp_size;
    const int warps_per_block = blockDim.x / warp_size;
    const int i = blockIdx.x * warps_per_block + warp_in_block;
    if (i >= n) return;

    const float G = 1.0f;
    const float softening = 0.001f;
    const Particle target = in[i];

    float fx = 0.0f;
    float fy = 0.0f;
    float fz = 0.0f;

    for (int j = lane; j < n;) {
        if (i != j) {
            float dx = in[j].x - target.x;
            float dy = in[j].y - target.y;
            float dz = in[j].z - target.z;

            float distSq = dx * dx + dy * dy + dz * dz + softening;
            float dist = sqrtf(distSq);
            float f = (G * target.mass * in[j].mass) / (distSq * dist);

            fx += f * dx;
            fy += f * dy;
            fz += f * dz;
        }

        if (n - j <= warp_size) break;
        j += warp_size;
    }

    for (int offset = warp_size / 2; offset > 0; offset >>= 1) {
        fx += __shfl_down_sync(0xffffffffu, fx, offset);
        fy += __shfl_down_sync(0xffffffffu, fy, offset);
        fz += __shfl_down_sync(0xffffffffu, fz, offset);
    }

    if (lane == 0) {
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
