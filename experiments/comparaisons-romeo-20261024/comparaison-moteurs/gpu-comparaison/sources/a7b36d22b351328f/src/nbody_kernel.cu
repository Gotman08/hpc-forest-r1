struct Particle {
    float x, y, z;
    float vx, vy, vz;
    float mass;
};

extern "C" __global__ void nbody_step_naive(const Particle* in, Particle* out, int n, float dt) {
    const int warp_width = 32;
    const int warps_per_block = blockDim.x / warp_width;
    const int warp_index = static_cast<int>(threadIdx.x) / warp_width;
    const int lane = static_cast<int>(threadIdx.x) % warp_width;
    const int target = static_cast<int>(blockIdx.x) * warps_per_block + warp_index;
    const bool active_target = target < n;

    // Inactive target warps still participate in block-wide barriers.
    Particle target_particle = {};
    if (active_target) {
        target_particle = in[target];
    }

    const int tile_size = 256;
    const float softening = 0.001f;
    extern __shared__ float source_tile[];

    float fx = 0.0f;
    float fy = 0.0f;
    float fz = 0.0f;

    // The shared tile is laid out as four 256-float planes: x, y, z, mass.
    // All eight target warps reuse each cooperatively loaded source tile.
    for (int tile_start = 0; tile_start < n;) {
        const int remaining = n - tile_start;
        const int tile_count = remaining < tile_size ? remaining : tile_size;
        const int load_index = static_cast<int>(threadIdx.x);

        if (load_index < tile_count) {
            const int source_index = tile_start + load_index;
            const Particle source = in[source_index];
            source_tile[load_index] = source.x;
            source_tile[tile_size + load_index] = source.y;
            source_tile[2 * tile_size + load_index] = source.z;
            source_tile[3 * tile_size + load_index] = source.mass;
        }
        __syncthreads();

        // Each lane processes its source indices in increasing order, as in T2.
        for (int offset = 0; offset < tile_count; offset += warp_width) {
            const int local_source = offset + lane;
            if (active_target && local_source < tile_count) {
                const int source_index = tile_start + local_source;
                if (source_index != target) {
                    const float dx = source_tile[local_source] - target_particle.x;
                    const float dy = source_tile[tile_size + local_source] - target_particle.y;
                    const float dz = source_tile[2 * tile_size + local_source] - target_particle.z;
                    const float distSq = dx * dx + dy * dy + dz * dz + softening;
                    const float dist = sqrtf(distSq);
                    const float source_mass = source_tile[3 * tile_size + local_source];
                    const float f = (target_particle.mass * source_mass) / (distSq * dist);

                    fx += f * dx;
                    fy += f * dy;
                    fz += f * dz;
                }
            }
        }
        __syncthreads();

        if (remaining <= tile_size) break;
        tile_start += tile_size;
    }

    // Every lane of a valid warp participates in all three reductions.
    const unsigned int mask = 0xffffffffu;
    fx += __shfl_down_sync(mask, fx, 16);
    fy += __shfl_down_sync(mask, fy, 16);
    fz += __shfl_down_sync(mask, fz, 16);
    fx += __shfl_down_sync(mask, fx, 8);
    fy += __shfl_down_sync(mask, fy, 8);
    fz += __shfl_down_sync(mask, fz, 8);
    fx += __shfl_down_sync(mask, fx, 4);
    fy += __shfl_down_sync(mask, fy, 4);
    fz += __shfl_down_sync(mask, fz, 4);
    fx += __shfl_down_sync(mask, fx, 2);
    fy += __shfl_down_sync(mask, fy, 2);
    fz += __shfl_down_sync(mask, fz, 2);
    fx += __shfl_down_sync(mask, fx, 1);
    fy += __shfl_down_sync(mask, fy, 1);
    fz += __shfl_down_sync(mask, fz, 1);

    if (lane == 0 && active_target) {
        Particle p = target_particle;
        p.vx += (fx / p.mass) * dt;
        p.vy += (fy / p.mass) * dt;
        p.vz += (fz / p.mass) * dt;
        p.x += p.vx * dt;
        p.y += p.vy * dt;
        p.z += p.vz * dt;
        out[target] = p;
    }
}
