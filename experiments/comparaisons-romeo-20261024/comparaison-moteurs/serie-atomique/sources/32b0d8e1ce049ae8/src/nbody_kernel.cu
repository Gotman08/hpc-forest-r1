struct Particle {
    float x, y, z;
    float vx, vy, vz;
    float mass;
};

struct SourceParticle {
    float x, y, z, mass;
};

extern "C" __global__ void nbody_step_naive(const Particle* in, Particle* out, int n, float dt) {
    extern __shared__ SourceParticle shared_sources[];

    const int block_size = static_cast<int>(blockDim.x);
    const int thread_index = static_cast<int>(threadIdx.x);
    const int i = static_cast<int>(blockIdx.x) * block_size + thread_index;
    const bool has_target = i < n;

    const float G = 1.0f;
    const float softening = 0.001f;

    float fx = 0.0f;
    float fy = 0.0f;
    float fz = 0.0f;
    Particle p;

    if (has_target) {
        p = in[i];
    }

    for (int tile_start = 0; tile_start < n; tile_start += block_size) {
        const int source_index = tile_start + thread_index;
        if (source_index < n) {
            const Particle source = in[source_index];
            shared_sources[thread_index].x = source.x;
            shared_sources[thread_index].y = source.y;
            shared_sources[thread_index].z = source.z;
            shared_sources[thread_index].mass = source.mass;
        }

        __syncthreads();

        const int remaining = n - tile_start;
        const int tile_count = remaining < block_size ? remaining : block_size;

        if (has_target) {
            for (int k = 0; k < tile_count; ++k) {
                const int j = tile_start + k;
                if (i == j) continue;

                const SourceParticle source = shared_sources[k];
                const float dx = source.x - p.x;
                const float dy = source.y - p.y;
                const float dz = source.z - p.z;

                const float distSq = dx * dx + dy * dy + dz * dz + softening;
                const float dist = sqrtf(distSq);
                const float f = (G * p.mass * source.mass) / (distSq * dist);

                fx += f * dx;
                fy += f * dy;
                fz += f * dz;
            }
        }

        __syncthreads();
    }

    if (has_target) {
        p.vx += (fx / p.mass) * dt;
        p.vy += (fy / p.mass) * dt;
        p.vz += (fz / p.mass) * dt;

        p.x += p.vx * dt;
        p.y += p.vy * dt;
        p.z += p.vz * dt;

        out[i] = p;
    }
}
