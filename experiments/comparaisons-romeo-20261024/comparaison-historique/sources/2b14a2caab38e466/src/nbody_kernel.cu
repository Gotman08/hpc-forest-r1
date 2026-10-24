// Structure of an AoS particle.
struct Particle {
    float x, y, z;
    float vx, vy, vz;
    float mass;
};

static constexpr int SOURCE_TILE = 384;

// One thread owns each output. The CTA cooperatively stages source particles
// and reuses each staged tile across its output threads.
extern "C" __global__ void nbody_step_naive(const Particle* in, Particle* out, int n, float dt) {
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

    for (int tile_start = 0; tile_start < n; tile_start += SOURCE_TILE) {
        const int remaining = n - tile_start;
        const int tile_count = remaining < SOURCE_TILE ? remaining : SOURCE_TILE;

        for (int k = threadIdx.x; k < tile_count; k += blockDim.x) {
            source_tile[k] = in[tile_start + k];
        }
        __syncthreads();

        if (valid_output) {
            for (int k = 0; k < tile_count; ++k) {
                const int j = tile_start + k;
                if (i == j) continue;

                float dx = source_tile[k].x - target.x;
                float dy = source_tile[k].y - target.y;
                float dz = source_tile[k].z - target.z;

                float distSq = dx * dx + dy * dy + dz * dz + softening;
                float dist = sqrtf(distSq);

                float f = (G * target.mass * source_tile[k].mass) / (distSq * dist);

                fx += f * dx;
                fy += f * dy;
                fz += f * dz;
            }
        }
        __syncthreads();
    }

    if (valid_output) {
        target.vx += (fx / target.mass) * dt;
        target.vy += (fy / target.mass) * dt;
        target.vz += (fz / target.mass) * dt;

        target.x += target.vx * dt;
        target.y += target.vy * dt;
        target.z += target.vz * dt;

        out[i] = target;
    }
}
