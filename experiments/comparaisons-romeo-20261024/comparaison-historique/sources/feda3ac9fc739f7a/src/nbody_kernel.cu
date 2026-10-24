struct Particle {
    float x, y, z;
    float vx, vy, vz;
    float mass;
};

extern "C" __global__ void nbody_step_naive(const Particle* in, Particle* out, int n, float dt) {
    const int tid = threadIdx.x;
    const int i = blockIdx.x * blockDim.x + tid;
    const bool active = i < n;

    Particle pi;
    if (active) {
        pi = in[i];
    }

    const float G = 1.0f;
    const float softening = 0.001f;
    float fx = 0.0f;
    float fy = 0.0f;
    float fz = 0.0f;

    extern __shared__ Particle source_tile[];
    const int tile_size = 256;
    int tile_start = 0;
    while (tile_start < n) {
        const int remaining = n - tile_start;
        const int tile_count = remaining < tile_size ? remaining : tile_size;

        // Threads cooperatively stage the sources; output-tail threads participate too.
        for (int k = tid; k < tile_size; k += blockDim.x) {
            if (k < tile_count) {
                source_tile[k] = in[tile_start + k];
            }
        }
        __syncthreads();

        if (active) {
            for (int k = 0; k < tile_count; ++k) {
                const int j = tile_start + k;
                if (i == j) continue;

                const float dx = source_tile[k].x - pi.x;
                const float dy = source_tile[k].y - pi.y;
                const float dz = source_tile[k].z - pi.z;

                const float distSq = dx * dx + dy * dy + dz * dz + softening;
                const float dist = sqrtf(distSq);
                const float f = (G * pi.mass * source_tile[k].mass) / (distSq * dist);

                fx += f * dx;
                fy += f * dy;
                fz += f * dz;
            }
        }

        // Ensure no thread still reads this tile before it is reused.
        __syncthreads();
        if (remaining <= tile_size) break;
        tile_start += tile_size;
    }

    if (!active) return;

    Particle p = pi;
    p.vx += (fx / p.mass) * dt;
    p.vy += (fy / p.mass) * dt;
    p.vz += (fz / p.mass) * dt;

    p.x += p.vx * dt;
    p.y += p.vy * dt;
    p.z += p.vz * dt;

    out[i] = p;
}
