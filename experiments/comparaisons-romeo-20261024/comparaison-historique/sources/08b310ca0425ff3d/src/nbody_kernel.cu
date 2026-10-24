// Structure "Array of Structures" : each thread group computes one target.
struct Particle {
    float x, y, z;
    float vx, vy, vz;
    float mass;
};

// Each 8-lane subgroup partitions a target's source reduction.
extern "C" __global__ void nbody_step_naive(const Particle* in, Particle* out, int n, float dt) {
    const int lane = threadIdx.x & 31;
    const int subgroup_lane = lane & 7;
    const int target = blockIdx.x * (blockDim.x / 8) + threadIdx.x / 8;

    float fx = 0.0f;
    float fy = 0.0f;
    float fz = 0.0f;
    Particle p;

    if (target < n) {
        p = in[target];

        const float G = 1.0f;
        const float softening = 0.001f;

        for (long long j = subgroup_lane; j < n; j += 8) {
            if (j == target) continue;

            const float dx = in[j].x - p.x;
            const float dy = in[j].y - p.y;
            const float dz = in[j].z - p.z;

            const float distSq = dx * dx + dy * dy + dz * dz + softening;
            const float dist = sqrtf(distSq);
            const float f = (G * p.mass * in[j].mass) / (distSq * dist);

            fx += f * dx;
            fy += f * dy;
            fz += f * dz;
        }
    }

    // Keep every warp lane participating, including lanes for invalid targets.
    for (int offset = 4; offset > 0; offset >>= 1) {
        fx += __shfl_down_sync(0xffffffffu, fx, offset, 8);
        fy += __shfl_down_sync(0xffffffffu, fy, offset, 8);
        fz += __shfl_down_sync(0xffffffffu, fz, offset, 8);
    }

    if (subgroup_lane == 0 && target < n) {
        p.vx += (fx / p.mass) * dt;
        p.vy += (fy / p.mass) * dt;
        p.vz += (fz / p.mass) * dt;

        p.x += p.vx * dt;
        p.y += p.vy * dt;
        p.z += p.vz * dt;

        out[target] = p;
    }
}
