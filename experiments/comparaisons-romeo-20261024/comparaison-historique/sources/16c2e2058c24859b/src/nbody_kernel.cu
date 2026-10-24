// Structure "Array of Structures" (AoS).
struct Particle {
    float x, y, z;
    float vx, vy, vz;
    float mass;
};

// Each thread updates two outputs while reusing each source particle load.
// items_per_block must equal 2 * block for this output mapping.
extern "C" __global__ void nbody_step_naive(const Particle* in, Particle* out, int n, float dt) {
    const int threads_per_block = static_cast<int>(blockDim.x);
    const int output_base = static_cast<int>(blockIdx.x) * (2 * threads_per_block);
    const int i0 = output_base + static_cast<int>(threadIdx.x);
    const int i1 = i0 + threads_per_block;
    const bool valid0 = i0 < n;
    const bool valid1 = i1 < n;

    if (!valid0 && !valid1) return;

    const float G = 1.0f;
    const float softening = 0.001f;

    Particle p0;
    Particle p1;
    float fx0 = 0.0f, fy0 = 0.0f, fz0 = 0.0f;
    float fx1 = 0.0f, fy1 = 0.0f, fz1 = 0.0f;

    if (valid0) p0 = in[i0];
    if (valid1) p1 = in[i1];

    for (int j = 0; j < n; ++j) {
        const float source_x = in[j].x;
        const float source_y = in[j].y;
        const float source_z = in[j].z;
        const float source_mass = in[j].mass;

        if (valid0 && i0 != j) {
            const float dx = source_x - p0.x;
            const float dy = source_y - p0.y;
            const float dz = source_z - p0.z;
            const float distSq = dx * dx + dy * dy + dz * dz + softening;
            const float dist = sqrtf(distSq);
            const float f = (G * p0.mass * source_mass) / (distSq * dist);
            fx0 += f * dx;
            fy0 += f * dy;
            fz0 += f * dz;
        }

        if (valid1 && i1 != j) {
            const float dx = source_x - p1.x;
            const float dy = source_y - p1.y;
            const float dz = source_z - p1.z;
            const float distSq = dx * dx + dy * dy + dz * dz + softening;
            const float dist = sqrtf(distSq);
            const float f = (G * p1.mass * source_mass) / (distSq * dist);
            fx1 += f * dx;
            fy1 += f * dy;
            fz1 += f * dz;
        }
    }

    if (valid0) {
        p0.vx += (fx0 / p0.mass) * dt;
        p0.vy += (fy0 / p0.mass) * dt;
        p0.vz += (fz0 / p0.mass) * dt;
        p0.x += p0.vx * dt;
        p0.y += p0.vy * dt;
        p0.z += p0.vz * dt;
        out[i0] = p0;
    }

    if (valid1) {
        p1.vx += (fx1 / p1.mass) * dt;
        p1.vy += (fy1 / p1.mass) * dt;
        p1.vz += (fz1 / p1.mass) * dt;
        p1.x += p1.vx * dt;
        p1.y += p1.vy * dt;
        p1.z += p1.vz * dt;
        out[i1] = p1;
    }
}
