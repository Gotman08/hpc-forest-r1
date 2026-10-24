struct Particle {
    float x, y, z;
    float vx, vy, vz;
    float mass;
};

__device__ __forceinline__ void accumulate_source(
    const Particle& target,
    int target_index,
    int source_index,
    float sx,
    float sy,
    float sz,
    float source_mass,
    float& fx,
    float& fy,
    float& fz) {
    if (target_index == source_index) return;

    const float G = 1.0f;
    const float softening = 0.001f;
    const float dx = sx - target.x;
    const float dy = sy - target.y;
    const float dz = sz - target.z;

    const float distSq = dx * dx + dy * dy + dz * dz + softening;
    const float dist = sqrtf(distSq);
    const float f = (G * target.mass * source_mass) / (distSq * dist);

    fx += f * dx;
    fy += f * dy;
    fz += f * dz;
}

extern "C" __global__ void nbody_step_naive(const Particle* in, Particle* out, int n, float dt) {
    const long long first_index =
        static_cast<long long>(blockIdx.x) * blockDim.x * 2 + threadIdx.x;
    const long long second_index = first_index + blockDim.x;
    const bool first_valid = first_index < n;
    const bool second_valid = second_index < n;

    if (!first_valid && !second_valid) return;

    Particle first;
    Particle second;
    if (first_valid) first = in[first_index];
    if (second_valid) second = in[second_index];

    float fx_first = 0.0f;
    float fy_first = 0.0f;
    float fz_first = 0.0f;
    float fx_second = 0.0f;
    float fy_second = 0.0f;
    float fz_second = 0.0f;

    for (int j = 0; j < n; ++j) {
        const Particle source = in[j];
        const float sx = source.x;
        const float sy = source.y;
        const float sz = source.z;
        const float source_mass = source.mass;

        if (first_valid) {
            accumulate_source(first, static_cast<int>(first_index), j,
                              sx, sy, sz, source_mass,
                              fx_first, fy_first, fz_first);
        }
        if (second_valid) {
            accumulate_source(second, static_cast<int>(second_index), j,
                              sx, sy, sz, source_mass,
                              fx_second, fy_second, fz_second);
        }
    }

    if (first_valid) {
        first.vx += (fx_first / first.mass) * dt;
        first.vy += (fy_first / first.mass) * dt;
        first.vz += (fz_first / first.mass) * dt;
        first.x += first.vx * dt;
        first.y += first.vy * dt;
        first.z += first.vz * dt;
        out[first_index] = first;
    }

    if (second_valid) {
        second.vx += (fx_second / second.mass) * dt;
        second.vy += (fy_second / second.mass) * dt;
        second.vz += (fz_second / second.mass) * dt;
        second.x += second.vx * dt;
        second.y += second.vy * dt;
        second.z += second.vz * dt;
        out[second_index] = second;
    }
}
