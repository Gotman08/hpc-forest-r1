struct Particle {
    float x, y, z;
    float vx, vy, vz;
    float mass;
};

struct SharedSource {
    float x, y, z, mass;
};

extern "C" __global__ void nbody_step_naive(const Particle* in, Particle* out, int n, float dt) {
    constexpr int warp_width = 32;
    constexpr int source_tile_size = 512;
    __shared__ SharedSource source_tile[source_tile_size];

    const int thread = static_cast<int>(threadIdx.x);
    const int lane = thread & (warp_width - 1);
    const int warp_in_block = thread / warp_width;
    const int warps_per_block = static_cast<int>(blockDim.x) / warp_width;

    // launch.json maps one output particle to each warp.
    const long long output_index = static_cast<long long>(blockIdx.x) * warps_per_block + warp_in_block;
    const bool active = output_index < n;
    const int i = static_cast<int>(output_index);

    Particle target;
    if (active) {
        target = in[i];
    }

    const float G = 1.0f;
    const float softening = 0.001f;
    float fx = 0.0f;
    float fy = 0.0f;
    float fz = 0.0f;

    int tile_start = 0;
    while (tile_start < n) {
        const int remaining = n - tile_start;
        const int tile_count = remaining < source_tile_size ? remaining : source_tile_size;

        if (thread < tile_count) {
            const Particle source = in[tile_start + thread];
            source_tile[thread].x = source.x;
            source_tile[thread].y = source.y;
            source_tile[thread].z = source.z;
            source_tile[thread].mass = source.mass;
        }
        __syncthreads();

        if (active) {
            // Preserve each lane's source order while reusing the staged tile across output warps.
            for (int k = lane; k < tile_count; k += warp_width) {
                const int j = tile_start + k;
                if (j == i) continue;

                const SharedSource source = source_tile[k];
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

        // Inactive output warps must also reach both block-wide barriers.
        __syncthreads();
        tile_start += tile_count;
    }

    for (int offset = warp_width / 2; offset > 0; offset >>= 1) {
        fx += __shfl_down_sync(0xffffffffu, fx, offset);
        fy += __shfl_down_sync(0xffffffffu, fy, offset);
        fz += __shfl_down_sync(0xffffffffu, fz, offset);
    }

    if (lane == 0 && active) {
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
