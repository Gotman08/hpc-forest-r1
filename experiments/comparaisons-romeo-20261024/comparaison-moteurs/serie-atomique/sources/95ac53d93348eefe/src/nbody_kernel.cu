struct Particle {
    float x, y, z;
    float vx, vy, vz;
    float mass;
};

struct SharedSource {
    float x, y, z, mass;
};

extern "C" __global__ void nbody_step_naive(const Particle* in, Particle* out, int n, float dt) {
    __shared__ SharedSource source_tile[256];

    const int lane = static_cast<int>(threadIdx.x);
    const int i = static_cast<int>(blockIdx.x * blockDim.x + threadIdx.x);
    const bool active = i < n;

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
        const int tile_count = remaining < 256 ? remaining : 256;

        for (int k = lane; k < tile_count; k += blockDim.x) {
            const Particle source = in[tile_start + k];
            source_tile[k].x = source.x;
            source_tile[k].y = source.y;
            source_tile[k].z = source.z;
            source_tile[k].mass = source.mass;
        }
        __syncthreads();

        if (active) {
            for (int k = 0; k < tile_count; ++k) {
                const int j = tile_start + k;
                if (i == j) continue;

                const SharedSource source = source_tile[k];
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
        tile_start += tile_count;
    }

    if (!active) return;

    Particle p = target;
    p.vx += (fx / p.mass) * dt;
    p.vy += (fy / p.mass) * dt;
    p.vz += (fz / p.mass) * dt;

    p.x += p.vx * dt;
    p.y += p.vy * dt;
    p.z += p.vz * dt;

    out[i] = p;
}
