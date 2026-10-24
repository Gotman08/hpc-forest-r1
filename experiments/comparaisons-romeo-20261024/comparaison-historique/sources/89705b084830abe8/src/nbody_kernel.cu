struct Particle {
    float x, y, z;
    float vx, vy, vz;
    float mass;
};

// Each thread updates four outputs while reusing each source particle load.
// The launch grid must use items_per_block == 4 * block.
extern "C" __global__ void nbody_step_naive(const Particle* in, Particle* out, int n, float dt) {
    const int items_per_thread = 4;
    const unsigned long long block_base =
        static_cast<unsigned long long>(blockIdx.x) * blockDim.x * items_per_thread;
    const unsigned long long i0 = block_base + threadIdx.x;
    const unsigned long long i1 = i0 + blockDim.x;
    const unsigned long long i2 = i1 + blockDim.x;
    const unsigned long long i3 = i2 + blockDim.x;
    const bool active0 = i0 < static_cast<unsigned long long>(n);
    const bool active1 = i1 < static_cast<unsigned long long>(n);
    const bool active2 = i2 < static_cast<unsigned long long>(n);
    const bool active3 = i3 < static_cast<unsigned long long>(n);

    if (!active0 && !active1 && !active2 && !active3) return;

    Particle p0;
    Particle p1;
    Particle p2;
    Particle p3;
    if (active0) p0 = in[i0];
    if (active1) p1 = in[i1];
    if (active2) p2 = in[i2];
    if (active3) p3 = in[i3];

    const float G = 1.0f;
    const float softening = 0.001f;
    float fx0 = 0.0f, fy0 = 0.0f, fz0 = 0.0f;
    float fx1 = 0.0f, fy1 = 0.0f, fz1 = 0.0f;
    float fx2 = 0.0f, fy2 = 0.0f, fz2 = 0.0f;
    float fx3 = 0.0f, fy3 = 0.0f, fz3 = 0.0f;

    for (int j = 0; j < n; ++j) {
        const float sx = in[j].x;
        const float sy = in[j].y;
        const float sz = in[j].z;
        const float sm = in[j].mass;

        if (active0 && i0 != j) {
            const float dx = sx - p0.x;
            const float dy = sy - p0.y;
            const float dz = sz - p0.z;
            const float distSq = dx * dx + dy * dy + dz * dz + softening;
            const float dist = sqrtf(distSq);
            const float f = (G * p0.mass * sm) / (distSq * dist);
            fx0 += f * dx;
            fy0 += f * dy;
            fz0 += f * dz;
        }

        if (active1 && i1 != j) {
            const float dx = sx - p1.x;
            const float dy = sy - p1.y;
            const float dz = sz - p1.z;
            const float distSq = dx * dx + dy * dy + dz * dz + softening;
            const float dist = sqrtf(distSq);
            const float f = (G * p1.mass * sm) / (distSq * dist);
            fx1 += f * dx;
            fy1 += f * dy;
            fz1 += f * dz;
        }

        if (active2 && i2 != j) {
            const float dx = sx - p2.x;
            const float dy = sy - p2.y;
            const float dz = sz - p2.z;
            const float distSq = dx * dx + dy * dy + dz * dz + softening;
            const float dist = sqrtf(distSq);
            const float f = (G * p2.mass * sm) / (distSq * dist);
            fx2 += f * dx;
            fy2 += f * dy;
            fz2 += f * dz;
        }

        if (active3 && i3 != j) {
            const float dx = sx - p3.x;
            const float dy = sy - p3.y;
            const float dz = sz - p3.z;
            const float distSq = dx * dx + dy * dy + dz * dz + softening;
            const float dist = sqrtf(distSq);
            const float f = (G * p3.mass * sm) / (distSq * dist);
            fx3 += f * dx;
            fy3 += f * dy;
            fz3 += f * dz;
        }
    }

    if (active0) {
        p0.vx += (fx0 / p0.mass) * dt;
        p0.vy += (fy0 / p0.mass) * dt;
        p0.vz += (fz0 / p0.mass) * dt;
        p0.x += p0.vx * dt;
        p0.y += p0.vy * dt;
        p0.z += p0.vz * dt;
        out[i0] = p0;
    }

    if (active1) {
        p1.vx += (fx1 / p1.mass) * dt;
        p1.vy += (fy1 / p1.mass) * dt;
        p1.vz += (fz1 / p1.mass) * dt;
        p1.x += p1.vx * dt;
        p1.y += p1.vy * dt;
        p1.z += p1.vz * dt;
        out[i1] = p1;
    }

    if (active2) {
        p2.vx += (fx2 / p2.mass) * dt;
        p2.vy += (fy2 / p2.mass) * dt;
        p2.vz += (fz2 / p2.mass) * dt;
        p2.x += p2.vx * dt;
        p2.y += p2.vy * dt;
        p2.z += p2.vz * dt;
        out[i2] = p2;
    }

    if (active3) {
        p3.vx += (fx3 / p3.mass) * dt;
        p3.vy += (fy3 / p3.mass) * dt;
        p3.vz += (fz3 / p3.mass) * dt;
        p3.x += p3.vx * dt;
        p3.y += p3.vy * dt;
        p3.z += p3.vz * dt;
        out[i3] = p3;
    }
}
