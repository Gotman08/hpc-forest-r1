struct Particle {
    float x, y, z;
    float vx, vy, vz;
    float mass;
};

extern "C" __global__ void nbody_step_naive(const Particle* in, Particle* out, int n, float dt) {
    constexpr int COARSEN = 3;
    const unsigned int count = n > 0 ? static_cast<unsigned int>(n) : 0u;
    const unsigned int first = blockIdx.x * (blockDim.x * COARSEN) + threadIdx.x;
    if (first >= count) return;

    Particle target[COARSEN];
    unsigned int target_index[COARSEN];
    bool active[COARSEN];
    float fx[COARSEN];
    float fy[COARSEN];
    float fz[COARSEN];

    #pragma unroll
    for (int k = 0; k < COARSEN; ++k) {
        const unsigned int idx = first + static_cast<unsigned int>(k) * blockDim.x;
        target_index[k] = idx;
        active[k] = idx < count;
        fx[k] = 0.0f;
        fy[k] = 0.0f;
        fz[k] = 0.0f;
        if (active[k]) target[k] = in[idx];
    }

    const float G = 1.0f;
    const float softening = 0.001f;

    for (int j = 0; j < n; ++j) {
        const float sx = in[j].x;
        const float sy = in[j].y;
        const float sz = in[j].z;
        const float sm = in[j].mass;

        #pragma unroll
        for (int k = 0; k < COARSEN; ++k) {
            if (!active[k] || target_index[k] == static_cast<unsigned int>(j)) continue;

            const float dx = sx - target[k].x;
            const float dy = sy - target[k].y;
            const float dz = sz - target[k].z;

            const float distSq = dx * dx + dy * dy + dz * dz + softening;
            const float dist = sqrtf(distSq);
            const float f = (G * target[k].mass * sm) / (distSq * dist);

            fx[k] += f * dx;
            fy[k] += f * dy;
            fz[k] += f * dz;
        }
    }

    #pragma unroll
    for (int k = 0; k < COARSEN; ++k) {
        if (!active[k]) continue;

        target[k].vx += (fx[k] / target[k].mass) * dt;
        target[k].vy += (fy[k] / target[k].mass) * dt;
        target[k].vz += (fz[k] / target[k].mass) * dt;

        target[k].x += target[k].vx * dt;
        target[k].y += target[k].vy * dt;
        target[k].z += target[k].vz * dt;

        out[target_index[k]] = target[k];
    }
}
