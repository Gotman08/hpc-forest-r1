struct Particle {
    float x, y, z;
    float vx, vy, vz;
    float mass;
};

struct SourceParticle {
    float x, y, z, mass;
};

extern "C" __global__ void nbody_step_naive(const Particle* in, Particle* out, int n, float dt) {
    if (n <= 0) return;

    extern __shared__ SourceParticle source_tile[];

    const unsigned int particle_count = static_cast<unsigned int>(n);
    const unsigned int target_index = blockIdx.x * blockDim.x + threadIdx.x;
    const bool valid_target = target_index < particle_count;

    Particle target;
    float fx = 0.0f;
    float fy = 0.0f;
    float fz = 0.0f;

    if (valid_target) {
        target = in[target_index];
    }

    const float G = 1.0f;
    const float softening = 0.001f;

    for (unsigned int tile_start = 0; tile_start < particle_count; tile_start += blockDim.x) {
        const unsigned int source_index = tile_start + threadIdx.x;
        if (source_index < particle_count) {
            const Particle source = in[source_index];
            source_tile[threadIdx.x].x = source.x;
            source_tile[threadIdx.x].y = source.y;
            source_tile[threadIdx.x].z = source.z;
            source_tile[threadIdx.x].mass = source.mass;
        }
        __syncthreads();

        unsigned int tile_count = particle_count - tile_start;
        if (tile_count > blockDim.x) {
            tile_count = blockDim.x;
        }

        if (valid_target) {
            for (unsigned int offset = 0; offset < tile_count; ++offset) {
                const unsigned int j = tile_start + offset;
                if (target_index == j) continue;

                const SourceParticle source = source_tile[offset];
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

        out[target_index] = target;
    }
}
