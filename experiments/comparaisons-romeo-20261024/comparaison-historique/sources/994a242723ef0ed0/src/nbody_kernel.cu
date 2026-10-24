struct Particle {
    float x, y, z;
    float vx, vy, vz;
    float mass;
};

extern "C" __global__ void nbody_step_naive(const Particle* in, Particle* out, int n, float dt) {
    const int lane = threadIdx.x & 31;
    const int warp = threadIdx.x >> 5;
    const long long outputs_per_block = static_cast<long long>(blockDim.x / 32);
    const long long output_index = static_cast<long long>(blockIdx.x) * outputs_per_block + warp;
    if (output_index >= static_cast<long long>(n)) return;

    const int i = static_cast<int>(output_index);
    const Particle target = in[i];
    const float G = 1.0f;
    const float softening = 0.001f;

    float fx = 0.0f;
    float fy = 0.0f;
    float fz = 0.0f;

    for (long long source_index = lane; source_index < static_cast<long long>(n); source_index += 32) {
        const int j = static_cast<int>(source_index);
        if (i == j) continue;

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

    const unsigned int mask = 0xffffffffu;
    #pragma unroll
    for (int offset = 16; offset > 0; offset >>= 1) {
        fx += __shfl_down_sync(mask, fx, offset);
        fy += __shfl_down_sync(mask, fy, offset);
        fz += __shfl_down_sync(mask, fz, offset);
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
