struct Particle {
    float x, y, z;
    float vx, vy, vz;
    float mass;
};

extern "C" __global__ void nbody_step_naive(const Particle* in, Particle* out, int n, float dt) {
    extern __shared__ Particle sources[];

    const int thread = static_cast<int>(threadIdx.x);
    const int block_size = static_cast<int>(blockDim.x);
    const int i = static_cast<int>(blockIdx.x) * block_size + thread;

    const float G = 1.0f;
    const float softening = 0.001f;

    float fx = 0.0f;
    float fy = 0.0f;
    float fz = 0.0f;

    // All CTA threads participate in staging and synchronization, including
    // threads whose output index is outside the final partial block.
    for (int tile_start = 0; tile_start < n;) {
        const int remaining = n - tile_start;
        const int tile_count = remaining < block_size ? remaining : block_size;
        const int source_index = tile_start + thread;
        if (source_index < n) {
            sources[thread] = in[source_index];
        }
        __syncthreads();

        if (i < n) {
            for (int k = 0; k < tile_count; ++k) {
                const int j = tile_start + k;
                if (i == j) continue;

                const Particle source = sources[k];
                float dx = source.x - in[i].x;
                float dy = source.y - in[i].y;
                float dz = source.z - in[i].z;

                float distSq = dx * dx + dy * dy + dz * dz + softening;
                float dist = sqrtf(distSq);

                float f = (G * in[i].mass * source.mass) / (distSq * dist);

                fx += f * dx;
                fy += f * dy;
                fz += f * dz;
            }
        }
        __syncthreads();
        tile_start += tile_count;
    }

    if (i >= n) return;

    Particle p = in[i];
    p.vx += (fx / p.mass) * dt;
    p.vy += (fy / p.mass) * dt;
    p.vz += (fz / p.mass) * dt;

    p.x += p.vx * dt;
    p.y += p.vy * dt;
    p.z += p.vz * dt;

    out[i] = p;
}
