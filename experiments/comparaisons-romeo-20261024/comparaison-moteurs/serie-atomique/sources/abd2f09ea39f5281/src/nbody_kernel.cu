struct Particle {
    float x, y, z;
    float vx, vy, vz;
    float mass;
};

extern "C" __global__ void nbody_step_naive(const Particle* in, Particle* out, int n, float dt) {
    if (n <= 0) return;

    // launch.json pairs 128 threads with 256 targets and 2048 shared bytes.
    // Each thread owns two targets; the shared tile holds 128 sources.
    constexpr unsigned int targets_per_thread = 2U;
    const unsigned int targets_per_block = blockDim.x * targets_per_thread;
    const unsigned int first_target = blockIdx.x * targets_per_block + threadIdx.x;
    const unsigned int second_target = first_target + blockDim.x;
    const unsigned int count = static_cast<unsigned int>(n);
    const bool has_first = first_target < count;
    const bool has_second = second_target < count;

    Particle p_first;
    Particle p_second;
    if (has_first) p_first = in[first_target];
    if (has_second) p_second = in[second_target];

    extern __shared__ float source_tile[];
    float* const tile_x = source_tile;
    float* const tile_y = source_tile + blockDim.x;
    float* const tile_z = source_tile + 2U * blockDim.x;
    float* const tile_mass = source_tile + 3U * blockDim.x;

    const float G = 1.0f;
    const float softening = 0.001f;
    float fx_first = 0.0f, fy_first = 0.0f, fz_first = 0.0f;
    float fx_second = 0.0f, fy_second = 0.0f, fz_second = 0.0f;

    // All threads participate in both barriers, including lanes with no target.
    for (unsigned int tile_start = 0; tile_start < count; tile_start += blockDim.x) {
        const unsigned int source_index = tile_start + threadIdx.x;
        if (source_index < count) {
            const Particle source = in[source_index];
            tile_x[threadIdx.x] = source.x;
            tile_y[threadIdx.x] = source.y;
            tile_z[threadIdx.x] = source.z;
            tile_mass[threadIdx.x] = source.mass;
        } else {
            tile_x[threadIdx.x] = 0.0f;
            tile_y[threadIdx.x] = 0.0f;
            tile_z[threadIdx.x] = 0.0f;
            tile_mass[threadIdx.x] = 0.0f;
        }
        __syncthreads();

        unsigned int tile_count = count - tile_start;
        if (tile_count > blockDim.x) tile_count = blockDim.x;

        if (has_first || has_second) {
            for (unsigned int k = 0; k < tile_count; ++k) {
                const unsigned int j = tile_start + k;
                const float sx = tile_x[k];
                const float sy = tile_y[k];
                const float sz = tile_z[k];
                const float smass = tile_mass[k];

                if (has_first && first_target != j) {
                    const float dx = sx - p_first.x;
                    const float dy = sy - p_first.y;
                    const float dz = sz - p_first.z;
                    const float distSq = dx * dx + dy * dy + dz * dz + softening;
                    const float dist = sqrtf(distSq);
                    const float f = (G * p_first.mass * smass) / (distSq * dist);
                    fx_first += f * dx;
                    fy_first += f * dy;
                    fz_first += f * dz;
                }

                if (has_second && second_target != j) {
                    const float dx = sx - p_second.x;
                    const float dy = sy - p_second.y;
                    const float dz = sz - p_second.z;
                    const float distSq = dx * dx + dy * dy + dz * dz + softening;
                    const float dist = sqrtf(distSq);
                    const float f = (G * p_second.mass * smass) / (distSq * dist);
                    fx_second += f * dx;
                    fy_second += f * dy;
                    fz_second += f * dz;
                }
            }
        }
        __syncthreads();
    }

    if (has_first) {
        p_first.vx += (fx_first / p_first.mass) * dt;
        p_first.vy += (fy_first / p_first.mass) * dt;
        p_first.vz += (fz_first / p_first.mass) * dt;
        p_first.x += p_first.vx * dt;
        p_first.y += p_first.vy * dt;
        p_first.z += p_first.vz * dt;
        out[first_target] = p_first;
    }

    if (has_second) {
        p_second.vx += (fx_second / p_second.mass) * dt;
        p_second.vy += (fy_second / p_second.mass) * dt;
        p_second.vz += (fz_second / p_second.mass) * dt;
        p_second.x += p_second.vx * dt;
        p_second.y += p_second.vy * dt;
        p_second.z += p_second.vz * dt;
        out[second_target] = p_second;
    }
}
