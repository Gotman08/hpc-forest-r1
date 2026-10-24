struct Particle {
    float x, y, z;
    float vx, vy, vz;
    float mass;
};

extern "C" __global__ void nbody_step_naive(const Particle* in, Particle* out, int n, float dt) {
    const int tile_size = 256;
    __shared__ float source_x[256];
    __shared__ float source_y[256];
    __shared__ float source_z[256];
    __shared__ float source_mass[256];

    const int thread_id = threadIdx.x;
    const int first_target = blockIdx.x * 256 + thread_id;
    const int second_target = first_target + blockDim.x;
    const bool first_valid = first_target < n;
    const bool second_valid = second_target < n;

    Particle first_particle;
    Particle second_particle;
    if (first_valid) {
        first_particle = in[first_target];
    }
    if (second_valid) {
        second_particle = in[second_target];
    }

    const float G = 1.0f;
    const float softening = 0.001f;
    float first_fx = 0.0f;
    float first_fy = 0.0f;
    float first_fz = 0.0f;
    float second_fx = 0.0f;
    float second_fy = 0.0f;
    float second_fz = 0.0f;

    for (int tile_start = 0; tile_start < n; tile_start += tile_size) {
        const int remaining = n - tile_start;
        const int tile_count = remaining < tile_size ? remaining : tile_size;

        // Each thread loads two sources for this 256-element tile.
        for (int k = thread_id; k < tile_size; k += blockDim.x) {
            if (k < tile_count) {
                const Particle source = in[tile_start + k];
                source_x[k] = source.x;
                source_y[k] = source.y;
                source_z[k] = source.z;
                source_mass[k] = source.mass;
            }
        }
        __syncthreads();

        for (int k = 0; k < tile_count; ++k) {
            const int j = tile_start + k;
            const float sx = source_x[k];
            const float sy = source_y[k];
            const float sz = source_z[k];
            const float sm = source_mass[k];

            if (first_valid && first_target != j) {
                const float dx = sx - first_particle.x;
                const float dy = sy - first_particle.y;
                const float dz = sz - first_particle.z;
                const float distSq = dx * dx + dy * dy + dz * dz + softening;
                const float dist = sqrtf(distSq);
                const float f = (G * first_particle.mass * sm) / (distSq * dist);
                first_fx += f * dx;
                first_fy += f * dy;
                first_fz += f * dz;
            }

            if (second_valid && second_target != j) {
                const float dx = sx - second_particle.x;
                const float dy = sy - second_particle.y;
                const float dz = sz - second_particle.z;
                const float distSq = dx * dx + dy * dy + dz * dz + softening;
                const float dist = sqrtf(distSq);
                const float f = (G * second_particle.mass * sm) / (distSq * dist);
                second_fx += f * dx;
                second_fy += f * dy;
                second_fz += f * dz;
            }
        }

        // All threads, including those without a valid target, must reach this barrier.
        __syncthreads();
    }

    if (first_valid) {
        first_particle.vx += (first_fx / first_particle.mass) * dt;
        first_particle.vy += (first_fy / first_particle.mass) * dt;
        first_particle.vz += (first_fz / first_particle.mass) * dt;
        first_particle.x += first_particle.vx * dt;
        first_particle.y += first_particle.vy * dt;
        first_particle.z += first_particle.vz * dt;
        out[first_target] = first_particle;
    }

    if (second_valid) {
        second_particle.vx += (second_fx / second_particle.mass) * dt;
        second_particle.vy += (second_fy / second_particle.mass) * dt;
        second_particle.vz += (second_fz / second_particle.mass) * dt;
        second_particle.x += second_particle.vx * dt;
        second_particle.y += second_particle.vy * dt;
        second_particle.z += second_particle.vz * dt;
        out[second_target] = second_particle;
    }
}
