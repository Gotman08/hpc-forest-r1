// Structure "Array of Structures" (AoS) : intuitive mais naïve sur GPU
// car elle empêche la coalescence parfaite des accès mémoire.
struct Particle {
    float x, y, z;
    float vx, vy, vz;
    float mass;
};

struct SourceParticle {
    float x, y, z, mass;
};

static constexpr int SOURCE_TILE_SIZE = 256;

// Each CTA stages source particles in shared-memory chunks. Each active
// thread still owns exactly one target and accumulates its output locally.
extern "C" __global__ void nbody_step_naive(const Particle* in, Particle* out, int n, float dt) {
    extern __shared__ SourceParticle source_tile[];

    const int i = blockIdx.x * blockDim.x + threadIdx.x;
    const bool active = i < n;
    Particle target;
    if (active) {
        target = in[i];
    }

    const float G = 1.0f;
    const float softening = 0.001f;

    float fx = 0.0f;
    float fy = 0.0f;
    float fz = 0.0f;

    for (int tile_begin = 0; tile_begin < n;) {
        int tile_size = n - tile_begin;
        if (tile_size > SOURCE_TILE_SIZE) {
            tile_size = SOURCE_TILE_SIZE;
        }

        for (int k = threadIdx.x; k < tile_size; k += blockDim.x) {
            const int source_index = tile_begin + k;
            source_tile[k].x = in[source_index].x;
            source_tile[k].y = in[source_index].y;
            source_tile[k].z = in[source_index].z;
            source_tile[k].mass = in[source_index].mass;
        }
        __syncthreads();

        if (active) {
            for (int k = 0; k < tile_size; ++k) {
                const int j = tile_begin + k;
                if (i == j) continue;

                const SourceParticle source = source_tile[k];
                float dx = source.x - target.x;
                float dy = source.y - target.y;
                float dz = source.z - target.z;

                float distSq = dx * dx + dy * dy + dz * dz + softening;
                const float invDist = rsqrtf(distSq);
                float invDistCube;
                if (invDist == 0.0f) {
                    invDistCube = 0.0f;
                } else {
                    const float invDistSq = invDist * invDist;
                    const float squareError = fmaf(distSq, invDistSq, -1.0f);
                    const float cubeCorrection = fmaf(-1.5f, squareError, 1.0f);
                    invDistCube = (invDistSq * invDist) * cubeCorrection;
                }

                float f = (G * target.mass * source.mass) * invDistCube;

                fx += f * dx;
                fy += f * dy;
                fz += f * dz;
            }
        }
        __syncthreads();
        tile_begin += tile_size;
    }

    if (!active) return;

    Particle p = target;
    p.vx += (fx / p.mass) * dt;
    p.vy += (fy / p.mass) * dt;
    p.vz += (fz / p.mass) * dt;

    p.x += p.vx * dt;
    p.y += p.vy * dt;
    p.z += p.vz * dt;

    out[i] = p;
}
