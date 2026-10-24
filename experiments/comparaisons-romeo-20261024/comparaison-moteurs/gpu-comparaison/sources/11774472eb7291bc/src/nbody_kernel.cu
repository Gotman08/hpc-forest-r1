// Structure "Array of Structures" (AoS).
struct Particle {
    float x, y, z;
    float vx, vy, vz;
    float mass;
};

#define SOURCE_TILE_SIZE 512

// Each thread computes one target while the CTA reuses staged source fields.
extern "C" __global__ void nbody_step_naive(const Particle* in, Particle* out, int n, float dt) {
    int i = blockIdx.x * blockDim.x + threadIdx.x;

    const float G = 1.0f;
    const float softening = 0.001f;

    float fx = 0.0f;
    float fy = 0.0f;
    float fz = 0.0f;

    __shared__ float source_x[SOURCE_TILE_SIZE];
    __shared__ float source_y[SOURCE_TILE_SIZE];
    __shared__ float source_z[SOURCE_TILE_SIZE];
    __shared__ float source_mass[SOURCE_TILE_SIZE];

    for (int tile_start = 0; tile_start < n;) {
        int tile_count = n - tile_start;
        if (tile_count > SOURCE_TILE_SIZE) {
            tile_count = SOURCE_TILE_SIZE;
        }

        for (int k = threadIdx.x; k < tile_count; k += blockDim.x) {
            int j = tile_start + k;
            source_x[k] = in[j].x;
            source_y[k] = in[j].y;
            source_z[k] = in[j].z;
            source_mass[k] = in[j].mass;
        }
        __syncthreads();

        if (i < n) {
            for (int k = 0; k < tile_count; ++k) {
                int j = tile_start + k;
                if (i == j) continue;

                float dx = source_x[k] - in[i].x;
                float dy = source_y[k] - in[i].y;
                float dz = source_z[k] - in[i].z;

                float distSq = dx * dx + dy * dy + dz * dz + softening;
                float dist = sqrtf(distSq);

                float f = (G * in[i].mass * source_mass[k]) / (distSq * dist);

                fx += f * dx;
                fy += f * dy;
                fz += f * dz;
            }
        }
        __syncthreads();

        tile_start += tile_count;
    }

    if (i < n) {
        Particle p = in[i];
        p.vx += (fx / p.mass) * dt;
        p.vy += (fy / p.mass) * dt;
        p.vz += (fz / p.mass) * dt;

        p.x += p.vx * dt;
        p.y += p.vy * dt;
        p.z += p.vz * dt;

        out[i] = p;
    }
}
