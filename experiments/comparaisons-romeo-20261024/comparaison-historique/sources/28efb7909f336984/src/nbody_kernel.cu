struct Particle {
    float x, y, z;
    float vx, vy, vz;
    float mass;
};

extern "C" __global__ void nbody_step_naive(const Particle* in, Particle* out, int n, float dt) {
    const int tile_size = 512;
    const int tid = (int)threadIdx.x;
    const int targets_per_block = 4 * (int)blockDim.x;
    const int first_target = (int)blockIdx.x * targets_per_block + tid;
    const int second_target = first_target + (int)blockDim.x;
    const int third_target = second_target + (int)blockDim.x;
    const int fourth_target = third_target + (int)blockDim.x;
    const bool first_valid = first_target < n;
    const bool second_valid = second_target < n;
    const bool third_valid = third_target < n;
    const bool fourth_valid = fourth_target < n;

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
    const float x2 = third_valid ? in[third_target].x : 0.0f;
    const float y2 = third_valid ? in[third_target].y : 0.0f;
    const float z2 = third_valid ? in[third_target].z : 0.0f;
    const float mass2 = third_valid ? in[third_target].mass : 0.0f;
    const float x3 = fourth_valid ? in[fourth_target].x : 0.0f;
    const float y3 = fourth_valid ? in[fourth_target].y : 0.0f;
    const float z3 = fourth_valid ? in[fourth_target].z : 0.0f;
    const float mass3 = fourth_valid ? in[fourth_target].mass : 0.0f;

    float fx0 = 0.0f;
    float fy0 = 0.0f;
    float fz0 = 0.0f;
    float fx1 = 0.0f;
    float fy1 = 0.0f;
    float fz1 = 0.0f;
    float fx2 = 0.0f;
    float fy2 = 0.0f;
    float fz2 = 0.0f;
    float fx3 = 0.0f;
    float fy3 = 0.0f;
    float fz3 = 0.0f;

    __shared__ float tile_x[512];
    __shared__ float tile_y[512];
    __shared__ float tile_z[512];
    __shared__ float tile_mass[512];

    for (int tile_start = 0; tile_start < n; tile_start += tile_size) {
        for (int k = tid; k < tile_size; k += (int)blockDim.x) {
            const int source_index = tile_start + k;
            if (source_index < n) {
                tile_x[k] = in[source_index].x;
                tile_y[k] = in[source_index].y;
                tile_z[k] = in[source_index].z;
                tile_mass[k] = in[source_index].mass;
            } else {
                tile_x[k] = 0.0f;
                tile_y[k] = 0.0f;
                tile_z[k] = 0.0f;
                tile_mass[k] = 0.0f;
            }
        }
        __syncthreads();

        const int remaining = n - tile_start;
        const int tile_count = remaining < tile_size ? remaining : tile_size;
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

            if (third_valid && third_target != j) {
                const float dx = sx - x2;
                const float dy = sy - y2;
                const float dz = sz - z2;
                const float distSq = dx * dx + dy * dy + dz * dz + softening;
                const float dist = sqrtf(distSq);
                const float f = (G * mass2 * smass) / (distSq * dist);
                fx2 += f * dx;
                fy2 += f * dy;
                fz2 += f * dz;
            }

            if (fourth_valid && fourth_target != j) {
                const float dx = sx - x3;
                const float dy = sy - y3;
                const float dz = sz - z3;
                const float distSq = dx * dx + dy * dy + dz * dz + softening;
                const float dist = sqrtf(distSq);
                const float f = (G * mass3 * smass) / (distSq * dist);
                fx3 += f * dx;
                fy3 += f * dy;
                fz3 += f * dz;
            }
        }
        __syncthreads();
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

    if (third_valid) {
        Particle p = in[third_target];
        p.vx += (fx2 / p.mass) * dt;
        p.vy += (fy2 / p.mass) * dt;
        p.vz += (fz2 / p.mass) * dt;
        p.x += p.vx * dt;
        p.y += p.vy * dt;
        p.z += p.vz * dt;
        out[third_target] = p;
    }

    if (fourth_valid) {
        Particle p = in[fourth_target];
        p.vx += (fx3 / p.mass) * dt;
        p.vy += (fy3 / p.mass) * dt;
        p.vz += (fz3 / p.mass) * dt;
        p.x += p.vx * dt;
        p.y += p.vy * dt;
        p.z += p.vz * dt;
        out[fourth_target] = p;
    }
}
