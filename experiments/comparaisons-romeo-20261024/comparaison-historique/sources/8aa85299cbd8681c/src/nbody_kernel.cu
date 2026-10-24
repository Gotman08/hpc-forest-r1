struct Particle {
    float x, y, z;
    float vx, vy, vz;
    float mass;
};

extern "C" __global__ void nbody_step_naive(const Particle* in, Particle* out, int n, float dt) {
    __shared__ float warp_sums[15];

    const int target_idx = blockIdx.x;
    const int warp_id = threadIdx.x / 32;
    const int lane = threadIdx.x & 31;

    Particle target = {};
    if (target_idx < n) {
        target = in[target_idx];
    }

    const float G = 1.0f;
    const float softening = 0.001f;
    float fx = 0.0f;
    float fy = 0.0f;
    float fz = 0.0f;

    if (target_idx < n) {
        for (int j = warp_id * 32 + lane; j < n;) {
            if (j != target_idx) {
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

            if (n - j <= 160) {
                break;
            }
            j += 160;
        }
    }

    for (int offset = 16; offset > 0; offset >>= 1) {
        fx += __shfl_down_sync(0xffffffffu, fx, offset);
        fy += __shfl_down_sync(0xffffffffu, fy, offset);
        fz += __shfl_down_sync(0xffffffffu, fz, offset);
    }

    if (lane == 0) {
        warp_sums[warp_id * 3] = fx;
        warp_sums[warp_id * 3 + 1] = fy;
        warp_sums[warp_id * 3 + 2] = fz;
    }
    __syncthreads();

    if (threadIdx.x == 0 && target_idx < n) {
        fx = 0.0f;
        fy = 0.0f;
        fz = 0.0f;
        for (int warp = 0; warp < 5; ++warp) {
            fx += warp_sums[warp * 3];
            fy += warp_sums[warp * 3 + 1];
            fz += warp_sums[warp * 3 + 2];
        }

        Particle p = target;
        p.vx += (fx / p.mass) * dt;
        p.vy += (fy / p.mass) * dt;
        p.vz += (fz / p.mass) * dt;

        p.x += p.vx * dt;
        p.y += p.vy * dt;
        p.z += p.vz * dt;

        out[target_idx] = p;
    }
}
