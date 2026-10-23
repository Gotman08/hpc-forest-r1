struct Particle {
    float x, y, z;
    float vx, vy, vz;
    float mass;
};

// N-body kernel with a 512-particle shared-memory source tile.
extern "C" __global__ void nbody_step_naive(const Particle* in, Particle* out, int n, float dt) {
    const int tile_size = 512;
    const long long particle_count = static_cast<long long>(n);
    const long long target_index =
        static_cast<long long>(blockIdx.x) * static_cast<long long>(blockDim.x) +
        static_cast<long long>(threadIdx.x);
    const bool target_valid = target_index < particle_count;

    Particle target;
    if (target_valid) {
        target = in[static_cast<int>(target_index)];
    }

    const float G = 1.0f;
    const float softening = 0.001f;
    float fx = 0.0f;
    float fy = 0.0f;
    float fz = 0.0f;

    __shared__ Particle source_tile[512];

    for (long long tile_start = 0; tile_start < particle_count; tile_start += tile_size) {
        // Each 256-thread block loads two source particles per thread.
        for (int tile_index = static_cast<int>(threadIdx.x);
             tile_index < tile_size;
             tile_index += static_cast<int>(blockDim.x)) {
            const long long source_index = tile_start + tile_index;
            if (source_index < particle_count) {
                source_tile[tile_index] = in[static_cast<int>(source_index)];
            }
        }
        __syncthreads();

        const long long remaining = particle_count - tile_start;
        const int tile_count = remaining < tile_size ? static_cast<int>(remaining) : tile_size;
        if (target_valid) {
            for (int k = 0; k < tile_count; ++k) {
                const long long source_index = tile_start + k;
                if (target_index == source_index) continue;

                const float dx = source_tile[k].x - target.x;
                const float dy = source_tile[k].y - target.y;
                const float dz = source_tile[k].z - target.z;

                const float distSq = dx * dx + dy * dy + dz * dz + softening;
                const float dist = sqrtf(distSq);
                const float f = (G * target.mass * source_tile[k].mass) / (distSq * dist);

                fx += f * dx;
                fy += f * dy;
                fz += f * dz;
            }
        }
        __syncthreads();
    }

    if (!target_valid) return;

    Particle p = target;
    p.vx += (fx / p.mass) * dt;
    p.vy += (fy / p.mass) * dt;
    p.vz += (fz / p.mass) * dt;

    p.x += p.vx * dt;
    p.y += p.vy * dt;
    p.z += p.vz * dt;

    out[static_cast<int>(target_index)] = p;
}
