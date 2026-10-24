// Chaque warp actif réutilise ses sources pour deux cibles par lane.
struct Particle {
    float x, y, z;
    float vx, vy, vz;
    float mass;
};

extern "C" __global__ void nbody_step_naive(const Particle* in, Particle* out, int n, float dt) {
    const int lane = threadIdx.x & 31;
    const int warp = threadIdx.x >> 5;
    const int active_warps = blockDim.x / 32;

    // Avec 128 threads, les quatre warps du bloc couvrent 256 cibles.
    if (warp >= active_warps) return;

    const int warp_base = blockIdx.x * blockDim.x * 2 + warp * 64;
    if (warp_base >= n) return;

    const int i0 = warp_base + lane;
    const int i1 = i0 + 32;
    const bool valid0 = i0 < n;
    const bool valid1 = i1 < n;

    Particle p0 = {};
    Particle p1 = {};
    if (valid0) p0 = in[i0];
    if (valid1) p1 = in[i1];

    const float G = 1.0f;
    const float softening = 0.001f;
    float fx0 = 0.0f, fy0 = 0.0f, fz0 = 0.0f;
    float fx1 = 0.0f, fy1 = 0.0f, fz1 = 0.0f;

    // Toutes les lanes d'un warp actif restent présentes aux shuffles,
    // y compris celles dont une ou deux cibles sont hors de la queue.
    for (int base = 0; base < n; ) {
        const int source_index = base + lane;
        float sx_lane = 0.0f;
        float sy_lane = 0.0f;
        float sz_lane = 0.0f;
        float sm_lane = 0.0f;
        if (source_index < n) {
            const Particle& source = in[source_index];
            sx_lane = source.x;
            sy_lane = source.y;
            sz_lane = source.z;
            sm_lane = source.mass;
        }

        const int remaining = n - base;
        const int source_count = remaining < 32 ? remaining : 32;
        for (int s = 0; s < source_count; ++s) {
            const int j = base + s;
            const float sx = __shfl_sync(0xffffffffu, sx_lane, s);
            const float sy = __shfl_sync(0xffffffffu, sy_lane, s);
            const float sz = __shfl_sync(0xffffffffu, sz_lane, s);
            const float sm = __shfl_sync(0xffffffffu, sm_lane, s);

            if (j < n) {
                if (valid0 && i0 != j) {
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
                if (valid1 && i1 != j) {
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
            }
        }

        if (remaining <= 32) break;
        base += 32;
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
