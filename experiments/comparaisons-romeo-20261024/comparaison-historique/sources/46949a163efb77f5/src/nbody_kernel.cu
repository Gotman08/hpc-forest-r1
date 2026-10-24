struct Particle {
    float x, y, z;
    float vx, vy, vz;
    float mass;
};

extern "C" __global__ void nbody_step_naive(const Particle* in, Particle* out, int n, float dt) {
    constexpr int warp_width = 32;
    constexpr int warps_per_target = 4;
    const int lane = threadIdx.x % warp_width;
    const int warp = threadIdx.x / warp_width;
    const int target_group = warp / warps_per_target;
    const int warp_in_target = warp % warps_per_target;
    const long long i = (long long)blockIdx.x * 2 + target_group;

    __shared__ float partial[2][warps_per_target][3];

    Particle target = {};
    if (i < n) {
        target = in[i];
    }

    float fx = 0.0f;
    float fy = 0.0f;
    float fz = 0.0f;

    const float G = 1.0f;
    const float softening = 0.001f;
    if (i < n) {
        for (long long j = (long long)warp_in_target * warp_width + lane;
             j < (long long)n;
             j += warps_per_target * warp_width) {
            if (i == j) continue;

            const Particle source = in[j];
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

    for (int offset = warp_width / 2; offset > 0; offset >>= 1) {
        fx += __shfl_down_sync(0xffffffffu, fx, offset);
        fy += __shfl_down_sync(0xffffffffu, fy, offset);
        fz += __shfl_down_sync(0xffffffffu, fz, offset);
    }

    if (lane == 0) {
        partial[target_group][warp_in_target][0] = fx;
        partial[target_group][warp_in_target][1] = fy;
        partial[target_group][warp_in_target][2] = fz;
    }

    __syncthreads();

    if (lane == 0 && warp_in_target == 0 && i < n) {
        float total_x = 0.0f;
        float total_y = 0.0f;
        float total_z = 0.0f;
        for (int w = 0; w < warps_per_target; ++w) {
            total_x += partial[target_group][w][0];
            total_y += partial[target_group][w][1];
            total_z += partial[target_group][w][2];
        }

        Particle p = target;
        p.vx += (total_x / p.mass) * dt;
        p.vy += (total_y / p.mass) * dt;
        p.vz += (total_z / p.mass) * dt;

        p.x += p.vx * dt;
        p.y += p.vy * dt;
        p.z += p.vz * dt;

        out[i] = p;
    }
}
