struct Particle {
    float x, y, z;
    float vx, vy, vz;
    float mass;
};

// Two adjacent targets per thread reuse each staged source particle.
extern "C" __global__ void nbody_step_naive(const Particle* in, Particle* out, int n, float dt) {
    const int tile_size = 512;
    const long long particle_count = static_cast<long long>(n);
    const long long output_stride =
        static_cast<long long>(gridDim.x) * static_cast<long long>(blockDim.x) * 2LL;

    const float G = 1.0f;
    const float softening = 0.001f;
    __shared__ Particle source_tile[512];

    // This loop bound is uniform within the block, so all threads reach both barriers.
    for (long long output_start =
             static_cast<long long>(blockIdx.x) * static_cast<long long>(blockDim.x) * 2LL;
         output_start < particle_count;
         output_start += output_stride) {
        const long long first_i =
            output_start + static_cast<long long>(threadIdx.x) * 2LL;
        const bool has0 = first_i < particle_count;
        const bool has1 = first_i + 1LL < particle_count;

        Particle p0;
        Particle p1;
        if (has0) p0 = in[static_cast<int>(first_i)];
        if (has1) p1 = in[static_cast<int>(first_i + 1LL)];

        float fx0 = 0.0f;
        float fy0 = 0.0f;
        float fz0 = 0.0f;
        float fx1 = 0.0f;
        float fy1 = 0.0f;
        float fz1 = 0.0f;

        for (long long tile_start = 0; tile_start < particle_count; tile_start += tile_size) {
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
            const int tile_count = remaining < tile_size
                ? static_cast<int>(remaining)
                : tile_size;

            for (int k = 0; k < tile_count; ++k) {
                const long long source_index = tile_start + k;
                const Particle source = source_tile[k];

                if (has0 && first_i != source_index) {
                    const float dx = source.x - p0.x;
                    const float dy = source.y - p0.y;
                    const float dz = source.z - p0.z;

                    const float distSq = dx * dx + dy * dy + dz * dz + softening;
                    const float dist = sqrtf(distSq);
                    const float f = (G * p0.mass * source.mass) / (distSq * dist);

                    fx0 += f * dx;
                    fy0 += f * dy;
                    fz0 += f * dz;
                }

                if (has1 && first_i + 1LL != source_index) {
                    const float dx = source.x - p1.x;
                    const float dy = source.y - p1.y;
                    const float dz = source.z - p1.z;

                    const float distSq = dx * dx + dy * dy + dz * dz + softening;
                    const float dist = sqrtf(distSq);
                    const float f = (G * p1.mass * source.mass) / (distSq * dist);

                    fx1 += f * dx;
                    fy1 += f * dy;
                    fz1 += f * dz;
                }
            }
            __syncthreads();
        }

        if (has0) {
            p0.vx += (fx0 / p0.mass) * dt;
            p0.vy += (fy0 / p0.mass) * dt;
            p0.vz += (fz0 / p0.mass) * dt;
            p0.x += p0.vx * dt;
            p0.y += p0.vy * dt;
            p0.z += p0.vz * dt;
            out[static_cast<int>(first_i)] = p0;
        }

        if (has1) {
            p1.vx += (fx1 / p1.mass) * dt;
            p1.vy += (fy1 / p1.mass) * dt;
            p1.vz += (fz1 / p1.mass) * dt;
            p1.x += p1.vx * dt;
            p1.y += p1.vy * dt;
            p1.z += p1.vz * dt;
            out[static_cast<int>(first_i + 1LL)] = p1;
        }
    }
}
