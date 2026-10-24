struct Particle {
    float x, y, z;
    float vx, vy, vz;
    float mass;
};

__device__ __forceinline__ void accumulate_source(
    const Particle& target,
    int target_index,
    int source_index,
    float sx,
    float sy,
    float sz,
    float source_mass,
    float& fx,
    float& fy,
    float& fz) {
    if (target_index == source_index) return;

    const float G = 1.0f;
    const float softening = 0.001f;
    const float dx = sx - target.x;
    const float dy = sy - target.y;
    const float dz = sz - target.z;

    const float distSq = dx * dx + dy * dy + dz * dz + softening;
    const float dist = sqrtf(distSq);
    const float f = (G * target.mass * source_mass) / (distSq * dist);

    fx += f * dx;
    fy += f * dy;
    fz += f * dz;
}

extern "C" __global__ void nbody_step_naive(const Particle* in, Particle* out, int n, float dt) {
    const long long block_base = static_cast<long long>(blockIdx.x) *
                                 static_cast<long long>(blockDim.x) * 4LL;
    const long long i0 = block_base + static_cast<long long>(threadIdx.x);
    const long long i1 = i0 + static_cast<long long>(blockDim.x);
    const long long i2 = i1 + static_cast<long long>(blockDim.x);
    const long long i3 = i2 + static_cast<long long>(blockDim.x);

    const bool valid0 = i0 < n;
    const bool valid1 = i1 < n;
    const bool valid2 = i2 < n;
    const bool valid3 = i3 < n;
    if (!valid0 && !valid1 && !valid2 && !valid3) return;

    Particle p0;
    Particle p1;
    Particle p2;
    Particle p3;
    if (valid0) p0 = in[i0];
    if (valid1) p1 = in[i1];
    if (valid2) p2 = in[i2];
    if (valid3) p3 = in[i3];

    float fx0 = 0.0f, fy0 = 0.0f, fz0 = 0.0f;
    float fx1 = 0.0f, fy1 = 0.0f, fz1 = 0.0f;
    float fx2 = 0.0f, fy2 = 0.0f, fz2 = 0.0f;
    float fx3 = 0.0f, fy3 = 0.0f, fz3 = 0.0f;

    for (int j = 0; j < n; ++j) {
        const Particle source = in[j];
        const float sx = source.x;
        const float sy = source.y;
        const float sz = source.z;
        const float source_mass = source.mass;

        if (valid0) {
            accumulate_source(p0, static_cast<int>(i0), j, sx, sy, sz, source_mass,
                              fx0, fy0, fz0);
        }
        if (valid1) {
            accumulate_source(p1, static_cast<int>(i1), j, sx, sy, sz, source_mass,
                              fx1, fy1, fz1);
        }
        if (valid2) {
            accumulate_source(p2, static_cast<int>(i2), j, sx, sy, sz, source_mass,
                              fx2, fy2, fz2);
        }
        if (valid3) {
            accumulate_source(p3, static_cast<int>(i3), j, sx, sy, sz, source_mass,
                              fx3, fy3, fz3);
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

    if (valid2) {
        p2.vx += (fx2 / p2.mass) * dt;
        p2.vy += (fy2 / p2.mass) * dt;
        p2.vz += (fz2 / p2.mass) * dt;
        p2.x += p2.vx * dt;
        p2.y += p2.vy * dt;
        p2.z += p2.vz * dt;
        out[i2] = p2;
    }

    if (valid3) {
        p3.vx += (fx3 / p3.mass) * dt;
        p3.vy += (fy3 / p3.mass) * dt;
        p3.vz += (fz3 / p3.mass) * dt;
        p3.x += p3.vx * dt;
        p3.y += p3.vy * dt;
        p3.z += p3.vz * dt;
        out[i3] = p3;
    }
}
