struct Particle {
    float x, y, z;
    float vx, vy, vz;
    float mass;
};

extern "C" __global__ void nbody_step_naive(const Particle* in, Particle* out, int n, float dt) {
    const int tile_size = 1024;
    const int tid = (int)threadIdx.x;
    const int first_target = (int)blockIdx.x * (2 * (int)blockDim.x) + tid;
    const int second_target = first_target + (int)blockDim.x;
    const bool first_valid = first_target < n;
    const bool second_valid = second_target < n;

    const float G = 1.0f;
    const float softening = 0.001f;

    const float x0 = first_valid ? in[first_target].x : 0.0f;
    const float y0 = first_valid ? in[first_target].y : 0.0f;
    const float z0 = first_valid ? in[first_target].z : 0.0f;
    const float mass0 = first_valid ? in[first_target].mass : 0.0f;
    const float x1 = second_valid ? in[second_target].x : 0.0f;
    const float y1 = second_valid ? in[second_target].y : 0.0f;
    const float z1 = second_valid ? in[second_target].z : 0.0f;
    const float mass1 = second_valid ? in[second_target].mass : 0.0f;

    float fx0 = 0.0f;
    float fy0 = 0.0f;
    float fz0 = 0.0f;
    float fx1 = 0.0f;
    float fy1 = 0.0f;
    float fz1 = 0.0f;

    __shared__ float tile_x[1024];
    __shared__ float tile_y[1024];
    __shared__ float tile_z[1024];
    __shared__ float tile_mass[1024];

    for (int tile_start = 0; tile_start < n;) {
        const int remaining = n - tile_start;
        const int tile_count = remaining < tile_size ? remaining : tile_size;

        for (int tile_slot = tid; tile_slot < tile_size; tile_slot += (int)blockDim.x) {
            if (tile_slot < tile_count) {
                const Particle source = in[tile_start + tile_slot];
                tile_x[tile_slot] = source.x;
                tile_y[tile_slot] = source.y;
                tile_z[tile_slot] = source.z;
                tile_mass[tile_slot] = source.mass;
            } else {
                tile_x[tile_slot] = 0.0f;
                tile_y[tile_slot] = 0.0f;
                tile_z[tile_slot] = 0.0f;
                tile_mass[tile_slot] = 0.0f;
            }
        }
        __syncthreads();

        for (int k = 0; k < tile_count; ++k) {
            const int j = tile_start + k;
            const float sx = tile_x[k];
            const float sy = tile_y[k];
            const float sz = tile_z[k];
            const float smass = tile_mass[k];

            if (first_valid && first_target != j) {
                const float dx = sx - x0;
                const float dy = sy - y0;
                const float dz = sz - z0;
                const float distSq = dx * dx + dy * dy + dz * dz + softening;
                const float dist = sqrtf(distSq);
                const float f = (G * mass0 * smass) / (distSq * dist);
                fx0 += f * dx;
                fy0 += f * dy;
                fz0 += f * dz;
            }

            if (second_valid && second_target != j) {
                const float dx = sx - x1;
                const float dy = sy - y1;
                const float dz = sz - z1;
                const float distSq = dx * dx + dy * dy + dz * dz + softening;
                const float dist = sqrtf(distSq);
                const float f = (G * mass1 * smass) / (distSq * dist);
                fx1 += f * dx;
                fy1 += f * dy;
                fz1 += f * dz;
            }
        }
        __syncthreads();
        tile_start += tile_count;
    }

    if (first_valid) {
        Particle p = in[first_target];
        p.vx += (fx0 / p.mass) * dt;
        p.vy += (fy0 / p.mass) * dt;
        p.vz += (fz0 / p.mass) * dt;
        p.x += p.vx * dt;
        p.y += p.vy * dt;
        p.z += p.vz * dt;
        out[first_target] = p;
    }

    if (second_valid) {
        Particle p = in[second_target];
        p.vx += (fx1 / p.mass) * dt;
        p.vy += (fy1 / p.mass) * dt;
        p.vz += (fz1 / p.mass) * dt;
        p.x += p.vx * dt;
        p.y += p.vy * dt;
        p.z += p.vz * dt;
        out[second_target] = p;
    }
}
