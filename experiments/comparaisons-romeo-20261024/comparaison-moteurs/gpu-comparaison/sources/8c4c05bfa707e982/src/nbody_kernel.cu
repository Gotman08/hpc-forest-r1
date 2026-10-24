#define SOURCE_TILE_SIZE 256

struct Particle {
    float x, y, z;
    float vx, vy, vz;
    float mass;
};

extern "C" __global__ void nbody_step_naive(const Particle* in, Particle* out, int n, float dt) {
    __shared__ float source_x[SOURCE_TILE_SIZE];
    __shared__ float source_y[SOURCE_TILE_SIZE];
    __shared__ float source_z[SOURCE_TILE_SIZE];
    __shared__ float source_mass[SOURCE_TILE_SIZE];

    int i = blockIdx.x * blockDim.x + threadIdx.x;
    bool active = i < n;

    Particle p;
    if (active) {
        p = in[i];
    }

    const float G = 1.0f;
    const float softening = 0.001f;

    float fx = 0.0f;
    float fy = 0.0f;
    float fz = 0.0f;

    for (int tile_start = 0; tile_start < n;) {
        int remaining = n - tile_start;
        int tile_count = remaining < SOURCE_TILE_SIZE ? remaining : SOURCE_TILE_SIZE;

        for (int k = (int)threadIdx.x; k < SOURCE_TILE_SIZE; k += (int)blockDim.x) {
            if (k < tile_count) {
                int j = tile_start + k;
                source_x[k] = in[j].x;
                source_y[k] = in[j].y;
                source_z[k] = in[j].z;
                source_mass[k] = in[j].mass;
            } else {
                source_x[k] = 0.0f;
                source_y[k] = 0.0f;
                source_z[k] = 0.0f;
                source_mass[k] = 0.0f;
            }
        }
        __syncthreads();

        if (active) {
            for (int k = 0; k < tile_count; k++) {
                int j = tile_start + k;
                if (i == j) continue;

                float dx = source_x[k] - p.x;
                float dy = source_y[k] - p.y;
                float dz = source_z[k] - p.z;

                float distSq = dx * dx + dy * dy + dz * dz + softening;
                float dist = sqrtf(distSq);

                float f = (G * p.mass * source_mass[k]) / (distSq * dist);

                fx += f * dx;
                fy += f * dy;
                fz += f * dz;
            }
        }
        __syncthreads();

        tile_start += tile_count;
    }

    if (active) {
        p.vx += (fx / p.mass) * dt;
        p.vy += (fy / p.mass) * dt;
        p.vz += (fz / p.mass) * dt;

        p.x += p.vx * dt;
        p.y += p.vy * dt;
        p.z += p.vz * dt;

        out[i] = p;
    }
}
