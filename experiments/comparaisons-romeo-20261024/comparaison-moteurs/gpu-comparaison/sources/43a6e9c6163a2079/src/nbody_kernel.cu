struct Particle {
    float x, y, z;
    float vx, vy, vz;
    float mass;
};

extern "C" __global__ void nbody_step_naive(const Particle* in, Particle* out, int n, float dt) {
    const int i = blockIdx.x * blockDim.x + threadIdx.x;
    const bool active = i < n;

    // All threads, including those without a target, participate in the barriers.
    Particle target;
    if (active) {
        target = in[i];
    }

    extern __shared__ Particle shared_sources[];

    const float G = 1.0f;
    const float softening = 0.001f;
    float fx = 0.0f;
    float fy = 0.0f;
    float fz = 0.0f;

    // The launch configuration sets both the block and source-tile size to 256.
    for (int tile_start = 0; tile_start < n; ) {
        const int remaining = n - tile_start;
        const int tile_count = remaining < blockDim.x ? remaining : blockDim.x;

        for (int offset = threadIdx.x; offset < tile_count; offset += blockDim.x) {
            shared_sources[offset] = in[tile_start + offset];
        }
        __syncthreads();

        if (active) {
            for (int k = 0; k < tile_count; ++k) {
                const int j = tile_start + k;
                if (i == j) continue;

                const Particle source = shared_sources[k];
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

        // Do not overwrite the shared tile until every active target has used it.
        __syncthreads();
        tile_start += tile_count;
    }

    if (active) {
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
