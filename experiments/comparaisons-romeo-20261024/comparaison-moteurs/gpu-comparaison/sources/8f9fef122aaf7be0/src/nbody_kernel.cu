struct Particle {
    float x, y, z;
    float vx, vy, vz;
    float mass;
};

extern "C" __global__ void nbody_step_naive(const Particle* in, Particle* out, int n, float dt) {
    constexpr int source_tile_size = 512;

    const int thread_id = static_cast<int>(threadIdx.x);
    const int target_index = static_cast<int>(blockIdx.x) * static_cast<int>(blockDim.x) + thread_id;
    const bool active_target = target_index < n;

    Particle target;
    if (active_target) {
        target = in[target_index];
    }

    extern __shared__ Particle source_tile[];

    const float G = 1.0f;
    const float softening = 0.001f;
    float fx = 0.0f;
    float fy = 0.0f;
    float fz = 0.0f;

    for (int tile_start = 0; tile_start < n;) {
        int tile_count = n - tile_start;
        if (tile_count > source_tile_size) {
            tile_count = source_tile_size;
        }

        for (int source_offset = thread_id; source_offset < tile_count; source_offset += static_cast<int>(blockDim.x)) {
            source_tile[source_offset] = in[tile_start + source_offset];
        }
        __syncthreads();

        if (active_target) {
            const int target_offset = target_index - tile_start;
            const bool target_in_tile = target_offset >= 0 && target_offset < tile_count;
            const int segment_count = target_in_tile ? 2 : 1;

            for (int segment = 0; segment < segment_count; ++segment) {
                const int source_begin = segment == 0 ? 0 : target_offset + 1;
                const int source_end = target_in_tile && segment == 0 ? target_offset : tile_count;

                for (int source_offset = source_begin; source_offset < source_end; ++source_offset) {
                    const Particle source = source_tile[source_offset];
                    const float dx = source.x - target.x;
                    const float dy = source.y - target.y;
                    const float dz = source.z - target.z;

                    const float distSq = dx * dx + dy * dy + dz * dz + softening;
                    const float invDist = rsqrtf(distSq);
                    const float invDist3 = invDist * invDist * invDist;
                    const float f = (G * target.mass * source.mass) * invDist3;

                    fx += f * dx;
                    fy += f * dy;
                    fz += f * dz;
                }
            }
        }

        __syncthreads();
        tile_start += tile_count;
    }

    if (active_target) {
        Particle p = target;
        p.vx += (fx / p.mass) * dt;
        p.vy += (fy / p.mass) * dt;
        p.vz += (fz / p.mass) * dt;

        p.x += p.vx * dt;
        p.y += p.vy * dt;
        p.z += p.vz * dt;

        out[target_index] = p;
    }
}
