// Each thread updates one target; each block cooperatively tiles source particles.
struct Particle {
    float x, y, z;
    float vx, vy, vz;
    float mass;
};

extern "C" __global__ void nbody_step_naive(const Particle* in, Particle* out, int n, float dt) {
    const int i = blockIdx.x * blockDim.x + threadIdx.x;
    const bool active = i < n;

    const float G = 1.0f;
    const float softening = 0.001f;

    float fx = 0.0f;
    float fy = 0.0f;
    float fz = 0.0f;
    Particle target;
    if (active) {
        target = in[i];
    }

    extern __shared__ Particle shared_sources[];

    for (int tile_start = 0; tile_start < n; tile_start += blockDim.x) {
        const int source_idx = tile_start + threadIdx.x;
        if (source_idx < n) {
            shared_sources[threadIdx.x] = in[source_idx];
        }
        __syncthreads();

        const int tile_end = (tile_start + blockDim.x < n) ? tile_start + blockDim.x : n;
        if (active) {
            for (int j = tile_start; j < tile_end; ++j) {
                if (i == j) continue;

                const Particle source = shared_sources[j - tile_start];
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
