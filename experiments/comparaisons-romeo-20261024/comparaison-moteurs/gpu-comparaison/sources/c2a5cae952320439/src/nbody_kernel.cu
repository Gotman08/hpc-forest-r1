// Source-particle tiling: each thread computes exactly one target.
struct Particle {
    float x, y, z;
    float vx, vy, vz;
    float mass;
};

struct SourceParticle {
    float x, y, z, mass;
};

extern "C" __global__ void nbody_step_naive(const Particle* in, Particle* out, int n, float dt) {
    extern __shared__ SourceParticle sources[];

    const int thread = static_cast<int>(threadIdx.x);
    const int block_size = static_cast<int>(blockDim.x);
    const int i = static_cast<int>(blockIdx.x) * block_size + thread;
    const bool valid_target = i < n;

    Particle target;
    if (valid_target) {
        target = in[i];
    }

    const float G = 1.0f;
    const float softening = 0.001f;
    float fx = 0.0f;
    float fy = 0.0f;
    float fz = 0.0f;

    for (int base = 0; base < n; base += block_size) {
        const int source_index = base + thread;
        if (source_index < n) {
            const Particle source = in[source_index];
            sources[thread].x = source.x;
            sources[thread].y = source.y;
            sources[thread].z = source.z;
            sources[thread].mass = source.mass;
        }
        __syncthreads();

        const int remaining = n - base;
        const int tile_count = remaining < block_size ? remaining : block_size;
        for (int k = 0; k < tile_count; ++k) {
            const int j = base + k;
            if (valid_target && i != j) {
                const SourceParticle source = sources[k];
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

    if (valid_target) {
        target.vx += (fx / target.mass) * dt;
        target.vy += (fy / target.mass) * dt;
        target.vz += (fz / target.mass) * dt;

        target.x += target.vx * dt;
        target.y += target.vy * dt;
        target.z += target.vz * dt;

        out[i] = target;
    }
}
