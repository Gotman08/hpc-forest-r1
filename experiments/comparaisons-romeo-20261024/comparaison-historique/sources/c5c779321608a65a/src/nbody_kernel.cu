struct Particle {
    float x, y, z;
    float vx, vy, vz;
    float mass;
};

extern "C" __global__ void nbody_step_naive(const Particle* in, Particle* out, int n, float dt) {
    constexpr int source_tile_size = 512;
    extern __shared__ Particle source_tile[];

    const int i = blockIdx.x * blockDim.x + threadIdx.x;
    const bool valid_output = i < n;
    Particle target;
    if (valid_output) {
        target = in[i];
    }

    const float G = 1.0f;
    const float softening = 0.001f;
    float fx = 0.0f;
    float fy = 0.0f;
    float fz = 0.0f;

    for (int tile_begin = 0; tile_begin < n; tile_begin += source_tile_size) {
        for (int k = threadIdx.x; k < source_tile_size; k += blockDim.x) {
            const int source_index = tile_begin + k;
            if (source_index < n) {
                source_tile[k] = in[source_index];
            }
        }
        __syncthreads();

        int tile_count = n - tile_begin;
        if (tile_count > source_tile_size) {
            tile_count = source_tile_size;
        }

        if (valid_output) {
            for (int k = 0; k < tile_count; ++k) {
                const int j = tile_begin + k;
                if (i == j) {
                    continue;
                }

                const Particle source = source_tile[k];
                const float dx = source.x - target.x;
                const float dy = source.y - target.y;
                const float dz = source.z - target.z;

                const float distSq = dx * dx + dy * dy + dz * dz + softening;
                const float dist = sqrtf(distSq);
                const float f = (G * target.mass * source.mass) / (distSq * dist);

                fx += f * dx;
                fy += f * dy;
                fz += f * dz;
            }
        }
        __syncthreads();
    }

    if (valid_output) {
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
