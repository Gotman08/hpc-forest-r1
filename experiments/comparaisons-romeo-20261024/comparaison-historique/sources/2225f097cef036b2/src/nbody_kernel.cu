struct Particle {
    float x, y, z;
    float vx, vy, vz;
    float mass;
};

static __device__ __forceinline__ void accumulate_source_force(
    const Particle* in, const Particle& p, int i, int j,
    float& fx, float& fy, float& fz) {
    if (j != i) {
        const float G = 1.0f;
        const float softening = 0.001f;
        float dx = in[j].x - p.x;
        float dy = in[j].y - p.y;
        float dz = in[j].z - p.z;

        float distSq = dx * dx + dy * dy + dz * dz + softening;
        float dist = sqrtf(distSq);
        float f = (G * p.mass * in[j].mass) / (distSq * dist);

        fx += f * dx;
        fy += f * dy;
        fz += f * dz;
    }
}

// One warp computes the force on each output particle.
extern "C" __global__ void nbody_step_naive(const Particle* in, Particle* out, int n, float dt) {
    const int lane = threadIdx.x & 31;
    const int warp = threadIdx.x >> 5;
    const int warps_per_block = blockDim.x >> 5;
    const int i = blockIdx.x * warps_per_block + warp;
    const bool valid = i < n;

    Particle p{};
    if (valid) p = in[i];

    float fx = 0.0f;
    float fy = 0.0f;
    float fz = 0.0f;

    // Group four consecutive source terms per lane without changing their order.
    if (valid) {
        int j = lane;
        for (; n - j > 96;) {
            accumulate_source_force(in, p, i, j, fx, fy, fz);
            accumulate_source_force(in, p, i, j + 32, fx, fy, fz);
            accumulate_source_force(in, p, i, j + 64, fx, fy, fz);
            accumulate_source_force(in, p, i, j + 96, fx, fy, fz);

            if (n - j <= 128) {
                j = n;
                break;
            }
            j += 128;
        }

        // At most three strided source terms remain for this lane.
        for (; j < n;) {
            accumulate_source_force(in, p, i, j, fx, fy, fz);
            if (n - j <= 32) break;
            j += 32;
        }
    }

    // Every configured block contains complete warps, so all lanes participate.
    const unsigned mask = 0xffffffffu;
    for (int offset = 16; offset > 0; offset >>= 1) {
        fx += __shfl_down_sync(mask, fx, offset);
        fy += __shfl_down_sync(mask, fy, offset);
        fz += __shfl_down_sync(mask, fz, offset);
    }

    if (lane == 0 && valid) {
        p.vx += (fx / p.mass) * dt;
        p.vy += (fy / p.mass) * dt;
        p.vz += (fz / p.mass) * dt;

        p.x += p.vx * dt;
        p.y += p.vy * dt;
        p.z += p.vz * dt;

        out[i] = p;
    }
}
