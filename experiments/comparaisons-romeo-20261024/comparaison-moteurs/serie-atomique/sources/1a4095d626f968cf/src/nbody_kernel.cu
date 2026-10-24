struct Particle {
    float x, y, z;
    float vx, vy, vz;
    float mass;
};

extern "C" __global__ void nbody_step_naive(const Particle* in, Particle* out, int n, float dt) {
    const int thread = threadIdx.x;
    const int i = blockIdx.x * blockDim.x + thread;

    extern __shared__ float tile[];
    float* shared_x = tile;
    float* shared_y = shared_x + blockDim.x;
    float* shared_z = shared_y + blockDim.x;
    float* shared_mass = shared_z + blockDim.x;

    Particle target;
    if (i < n) {
        target = in[i];
    }

    const float G = 1.0f;
    const float softening = 0.001f;
    float fx = 0.0f;
    float fy = 0.0f;
    float fz = 0.0f;

    int base = 0;
    while (base < n) {
        const int remaining = n - base;
        const int tile_count = remaining < blockDim.x ? remaining : blockDim.x;

        if (thread < tile_count) {
            const int source = base + thread;
            shared_x[thread] = in[source].x;
            shared_y[thread] = in[source].y;
            shared_z[thread] = in[source].z;
            shared_mass[thread] = in[source].mass;
        }
        __syncthreads();

        if (i < n) {
            for (int offset = 0; offset < tile_count; ++offset) {
                const int j = base + offset;
                if (i == j) continue;

                float dx = shared_x[offset] - target.x;
                float dy = shared_y[offset] - target.y;
                float dz = shared_z[offset] - target.z;

                float distSq = dx * dx + dy * dy + dz * dz + softening;
                float dist = sqrtf(distSq);

                float f = (G * target.mass * shared_mass[offset]) / (distSq * dist);

                fx += f * dx;
                fy += f * dy;
                fz += f * dz;
            }
        }
        __syncthreads();
        base += tile_count;
    }

    if (i < n) {
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
