struct Particle {
    float x, y, z;
    float vx, vy, vz;
    float mass;
};

extern "C" __global__ void nbody_step_naive(const Particle* in, Particle* out, int n, float dt) {
    const long long tile_start = static_cast<long long>(blockIdx.x) *
                                 (2LL * static_cast<long long>(blockDim.x));
    const long long i0 = tile_start + threadIdx.x;
    const long long i1 = i0 + blockDim.x;
    const bool valid0 = i0 < static_cast<long long>(n);
    const bool valid1 = i1 < static_cast<long long>(n);

    if (!valid0 && !valid1) return;

    const float G = 1.0f;
    const float softening = 0.001f;

    float x0 = 0.0f, y0 = 0.0f, z0 = 0.0f, mass0 = 0.0f;
    float x1 = 0.0f, y1 = 0.0f, z1 = 0.0f, mass1 = 0.0f;
    if (valid0) {
        const Particle target = in[i0];
        x0 = target.x;
        y0 = target.y;
        z0 = target.z;
        mass0 = target.mass;
    }
    if (valid1) {
        const Particle target = in[i1];
        x1 = target.x;
        y1 = target.y;
        z1 = target.z;
        mass1 = target.mass;
    }

    float fx0 = 0.0f, fy0 = 0.0f, fz0 = 0.0f;
    float fx1 = 0.0f, fy1 = 0.0f, fz1 = 0.0f;

    for (int j = 0; j < n; ++j) {
        const float source_x = in[j].x;
        const float source_y = in[j].y;
        const float source_z = in[j].z;
        const float source_mass = in[j].mass;

        if (valid0 && i0 != j) {
            const float dx = source_x - x0;
            const float dy = source_y - y0;
            const float dz = source_z - z0;
            const float distSq = dx * dx + dy * dy + dz * dz + softening;
            const float dist = sqrtf(distSq);
            const float f = (G * mass0 * source_mass) / (distSq * dist);
            fx0 += f * dx;
            fy0 += f * dy;
            fz0 += f * dz;
        }

        if (valid1 && i1 != j) {
            const float dx = source_x - x1;
            const float dy = source_y - y1;
            const float dz = source_z - z1;
            const float distSq = dx * dx + dy * dy + dz * dz + softening;
            const float dist = sqrtf(distSq);
            const float f = (G * mass1 * source_mass) / (distSq * dist);
            fx1 += f * dx;
            fy1 += f * dy;
            fz1 += f * dz;
        }
    }

    if (valid0) {
        Particle result = in[i0];
        result.vx += (fx0 / result.mass) * dt;
        result.vy += (fy0 / result.mass) * dt;
        result.vz += (fz0 / result.mass) * dt;
        result.x += result.vx * dt;
        result.y += result.vy * dt;
        result.z += result.vz * dt;
        out[i0] = result;
    }

    if (valid1) {
        Particle result = in[i1];
        result.vx += (fx1 / result.mass) * dt;
        result.vy += (fy1 / result.mass) * dt;
        result.vz += (fz1 / result.mass) * dt;
        result.x += result.vx * dt;
        result.y += result.vy * dt;
        result.z += result.vz * dt;
        out[i1] = result;
    }
}
