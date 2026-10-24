struct Particle {
    float x, y, z;
    float vx, vy, vz;
    float mass;
};

extern "C" __global__ void nbody_step_naive(const Particle* in, Particle* out, int n, float dt) {
    const int thread = static_cast<int>(threadIdx.x);
    const int block_size = static_cast<int>(blockDim.x);
    const long long global_i = static_cast<long long>(blockIdx.x) * block_size + thread;
    const bool active = global_i < n;
    const int i = active ? static_cast<int>(global_i) : -1;

    Particle target;
    if (active) {
        target = in[i];
    }

    float fx = 0.0f;
    float fy = 0.0f;
    float fz = 0.0f;

    const int tile_capacity = 256;
    extern __shared__ float shared_x[];
    float* shared_y = shared_x + tile_capacity;
    float* shared_z = shared_y + tile_capacity;
    float* shared_mass = shared_z + tile_capacity;

    const float G = 1.0f;
    const float softening = 0.001f;

    for (int tile_start = 0; tile_start < n;) {
        const int remaining = n - tile_start;
        const int tile_count = remaining < tile_capacity ? remaining : tile_capacity;

        for (int offset = thread; offset < tile_count; offset += block_size) {
            const Particle source = in[tile_start + offset];
            shared_x[offset] = source.x;
            shared_y[offset] = source.y;
            shared_z[offset] = source.z;
            shared_mass[offset] = source.mass;
        }
        __syncthreads();

        if (active) {
            for (int offset = 0; offset < tile_count; ++offset) {
                const int j = tile_start + offset;
                if (i == j) continue;

                const float dx = shared_x[offset] - target.x;
                const float dy = shared_y[offset] - target.y;
                const float dz = shared_z[offset] - target.z;

                const float distSq = dx * dx + dy * dy + dz * dz + softening;
                const float dist = sqrtf(distSq);
                const float f = (G * target.mass * shared_mass[offset]) / (distSq * dist);

                fx += f * dx;
                fy += f * dy;
                fz += f * dz;
            }
        }
        __syncthreads();

        tile_start += tile_count;
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
