// Each thread updates one target; each block cooperatively tiles source particles.
struct Particle {
    float x, y, z;
    float vx, vy, vz;
    float mass;
};

constexpr int TILE_SIZE = 512;

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

    for (int tile_start = 0; tile_start < n;) {
        const int remaining = n - tile_start;
        const int tile_count = (remaining < TILE_SIZE) ? remaining : TILE_SIZE;
        const int tile_end = tile_start + tile_count;

        for (int source_offset = threadIdx.x; source_offset < tile_count; source_offset += blockDim.x) {
            shared_sources[source_offset] = in[tile_start + source_offset];
        }
        __syncthreads();

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

        if (tile_count == remaining) {
            break;
        }
        tile_start += TILE_SIZE;
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
