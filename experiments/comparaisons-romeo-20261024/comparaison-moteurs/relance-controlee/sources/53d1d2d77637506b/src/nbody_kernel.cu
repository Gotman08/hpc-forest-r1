struct Particle {
    float x, y, z;
    float vx, vy, vz;
    float mass;
};
static_assert(sizeof(Particle) == 28, "Particle layout must remain 28 bytes");

struct SourceParticle {
    float x, y, z, mass;
};

extern "C" __global__ void nbody_step_naive(const Particle* in, Particle* out, int n, float dt) {
    const int tid = threadIdx.x;
    const long long linear = static_cast<long long>(blockIdx.x) * blockDim.x + tid;
    const bool valid = linear < n;
    const int i = valid ? static_cast<int>(linear) : -1;

    Particle p;
    if (valid) p = in[i];

    const float G = 1.0f;
    const float softening = 0.001f;
    float fx = 0.0f;
    float fy = 0.0f;
    float fz = 0.0f;
    __shared__ SourceParticle source_tile[256];

    for (long long base = 0; base < n; base += blockDim.x) {
        const long long source_index = base + tid;
        if (source_index < n) {
            source_tile[tid] = {in[source_index].x, in[source_index].y,
                                in[source_index].z, in[source_index].mass};
        } else {
            source_tile[tid] = {0.0f, 0.0f, 0.0f, 0.0f};
        }
        __syncthreads();

        if (valid) {
            for (int k = 0; k < blockDim.x && base + k < n; ++k) {
                const int j = static_cast<int>(base + k);
                if (i == j) continue;

                const SourceParticle s = source_tile[k];
                const float dx = s.x - p.x;
                const float dy = s.y - p.y;
                const float dz = s.z - p.z;
                const float distSq = dx * dx + dy * dy + dz * dz + softening;
                const float dist = sqrtf(distSq);
                const float f = (G * p.mass * s.mass) / (distSq * dist);
                fx += f * dx;
                fy += f * dy;
                fz += f * dz;
            }
        }
        __syncthreads();
    }

    if (valid) {
        p.vx += (fx / p.mass) * dt;
        p.vy += (fy / p.mass) * dt;
        p.vz += (fz / p.mass) * dt;
        p.x += p.vx * dt;
        p.y += p.vy * dt;
        p.z += p.vz * dt;
        out[i] = p;
    }
}
