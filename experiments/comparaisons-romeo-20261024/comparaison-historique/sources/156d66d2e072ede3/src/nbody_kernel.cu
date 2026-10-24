struct Particle {
    float x, y, z;
    float vx, vy, vz;
    float mass;
};

static constexpr int kSourceTileSize = 384;

extern "C" __global__ void nbody_step_naive(const Particle* in, Particle* out, int n, float dt) {
    const unsigned int output_index_u = blockIdx.x * blockDim.x + threadIdx.x;
    const bool valid_output = output_index_u < static_cast<unsigned int>(n);
    const int i = valid_output ? static_cast<int>(output_index_u) : 0;

    extern __shared__ Particle source_tile[];

    Particle p;
    if (valid_output) {
        p = in[i];
    }

    const float G = 1.0f;
    const float softening = 0.001f;
    float fx = 0.0f;
    float fy = 0.0f;
    float fz = 0.0f;

    const int lane = static_cast<int>(threadIdx.x);
    const int threads_per_block = static_cast<int>(blockDim.x);
    int source_base = 0;
    while (source_base < n) {
        const int remaining = n - source_base;
        const int tile_count = remaining < kSourceTileSize ? remaining : kSourceTileSize;

        for (int t = lane; t < tile_count; t += threads_per_block) {
            source_tile[t] = in[source_base + t];
        }
        __syncthreads();

        if (valid_output) {
            for (int t = 0; t < tile_count; ++t) {
                const int j = source_base + t;
                if (i == j) continue;

                const Particle source = source_tile[t];
                float dx = source.x - p.x;
                float dy = source.y - p.y;
                float dz = source.z - p.z;

                float distSq = dx * dx + dy * dy + dz * dz + softening;
                float dist = sqrtf(distSq);
                float f = (G * p.mass * source.mass) / (distSq * dist);

                fx += f * dx;
                fy += f * dy;
                fz += f * dz;
            }
        }
        __syncthreads();
        source_base += tile_count;
    }

    if (valid_output) {
        p.vx += (fx / p.mass) * dt;
        p.vy += (fy / p.mass) * dt;
        p.vz += (fz / p.mass) * dt;

        p.x += p.vx * dt;
        p.y += p.vy * dt;
        p.z += p.vz * dt;

        out[i] = p;
    }
}
