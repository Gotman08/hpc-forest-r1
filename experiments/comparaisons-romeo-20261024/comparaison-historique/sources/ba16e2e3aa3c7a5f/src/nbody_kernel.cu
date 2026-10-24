struct Particle {
    float x, y, z;
    float vx, vy, vz;
    float mass;
};

extern "C" __global__ void nbody_step_naive(const Particle* in, Particle* out, int n, float dt) {
    const int lanes_per_target = 16;
    const int targets_per_block = blockDim.x / lanes_per_target;
    const int group_in_block = threadIdx.x / lanes_per_target;
    const int lane_in_group = threadIdx.x % lanes_per_target;
    const int target = static_cast<int>(blockIdx.x * targets_per_block + group_in_block);

    float fx = 0.0f;
    float fy = 0.0f;
    float fz = 0.0f;
    Particle p;

    if (target < n) {
        p = in[target];

        for (long long source = lane_in_group; source < static_cast<long long>(n); source += lanes_per_target) {
            if (source == target) continue;

            float dx = in[source].x - p.x;
            float dy = in[source].y - p.y;
            float dz = in[source].z - p.z;

            float distSq = dx * dx + dy * dy + dz * dz + 0.001f;
            float dist = sqrtf(distSq);
            float f = (1.0f * p.mass * in[source].mass) / (distSq * dist);

            fx += f * dx;
            fy += f * dy;
            fz += f * dz;
        }
    }

    // Each 16-lane subgroup reduces independently; all lanes reach every shuffle.
    for (int offset = lanes_per_target / 2; offset > 0; offset >>= 1) {
        fx += __shfl_down_sync(0xffffffffu, fx, offset, lanes_per_target);
        fy += __shfl_down_sync(0xffffffffu, fy, offset, lanes_per_target);
        fz += __shfl_down_sync(0xffffffffu, fz, offset, lanes_per_target);
    }

    if (lane_in_group == 0 && target < n) {
        p.vx += (fx / p.mass) * dt;
        p.vy += (fy / p.mass) * dt;
        p.vz += (fz / p.mass) * dt;

        p.x += p.vx * dt;
        p.y += p.vy * dt;
        p.z += p.vz * dt;

        out[target] = p;
    }
}
