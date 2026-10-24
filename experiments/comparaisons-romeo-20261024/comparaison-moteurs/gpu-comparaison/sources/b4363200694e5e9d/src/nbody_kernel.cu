// Structure "Array of Structures" (AoS) : intuitive mais naïve sur GPU
// car elle empêche la coalescence parfaite des accès mémoire.
struct Particle {
    float x, y, z;
    float vx, vy, vz;
    float mass;
};

// Chaque thread calcule quatre cibles et réutilise les champs de la source.
// Avec block=128 et items_per_block=512, les quatre tuiles couvrent
// exactement les cibles attribuées au bloc.
extern "C" __global__ void nbody_step_naive(const Particle* in, Particle* out, int n, float dt) {
    int i0 = blockIdx.x * (blockDim.x * 4) + threadIdx.x;
    int i1 = i0 + blockDim.x;
    int i2 = i1 + blockDim.x;
    int i3 = i2 + blockDim.x;

    const bool active0 = i0 < n;
    const bool active1 = i1 < n;
    const bool active2 = i2 < n;
    const bool active3 = i3 < n;
    if (!(active0 || active1 || active2 || active3)) return;

    Particle p0, p1, p2, p3;
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

    for (int j = 0; j < n; j++) {
        const float source_x = in[j].x;
        const float source_y = in[j].y;
        const float source_z = in[j].z;
        const float source_mass = in[j].mass;

        if (active0 && i0 != j) {
            float dx = source_x - p0.x;
            float dy = source_y - p0.y;
            float dz = source_z - p0.z;
            float distSq = dx * dx + dy * dy + dz * dz + softening;
            float dist = sqrtf(distSq);
            float f = (G * p0.mass * source_mass) / (distSq * dist);
            fx0 += f * dx;
            fy0 += f * dy;
            fz0 += f * dz;
        }

        if (active1 && i1 != j) {
            float dx = source_x - p1.x;
            float dy = source_y - p1.y;
            float dz = source_z - p1.z;
            float distSq = dx * dx + dy * dy + dz * dz + softening;
            float dist = sqrtf(distSq);
            float f = (G * p1.mass * source_mass) / (distSq * dist);
            fx1 += f * dx;
            fy1 += f * dy;
            fz1 += f * dz;
        }

        if (active2 && i2 != j) {
            float dx = source_x - p2.x;
            float dy = source_y - p2.y;
            float dz = source_z - p2.z;
            float distSq = dx * dx + dy * dy + dz * dz + softening;
            float dist = sqrtf(distSq);
            float f = (G * p2.mass * source_mass) / (distSq * dist);
            fx2 += f * dx;
            fy2 += f * dy;
            fz2 += f * dz;
        }

        if (active3 && i3 != j) {
            float dx = source_x - p3.x;
            float dy = source_y - p3.y;
            float dz = source_z - p3.z;
            float distSq = dx * dx + dy * dy + dz * dz + softening;
            float dist = sqrtf(distSq);
            float f = (G * p3.mass * source_mass) / (distSq * dist);
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
