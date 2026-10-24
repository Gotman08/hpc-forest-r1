struct Particle {
    float x, y, z;
    float vx, vy, vz;
    float mass;
};

extern "C" __global__ void nbody_step_naive(const Particle* in, Particle* out, int n, float dt) {
    constexpr int SOURCE_TILE_SIZE = 1536;
    __shared__ float source_x[SOURCE_TILE_SIZE];
    __shared__ float source_y[SOURCE_TILE_SIZE];
    __shared__ float source_z[SOURCE_TILE_SIZE];
    __shared__ float source_mass[SOURCE_TILE_SIZE];

    const int i = blockIdx.x * blockDim.x + threadIdx.x;
    const bool valid_target = i < n;

    const float G = 1.0f;
    const float softening = 0.001f;

    float fx = 0.0f;
    float fy = 0.0f;
    float fz = 0.0f;

    for (int tile_start = 0; tile_start < n;) {
        int tile_count = n - tile_start;
        if (tile_count > SOURCE_TILE_SIZE) {
            tile_count = SOURCE_TILE_SIZE;
        }

        for (int source_offset = threadIdx.x;
             source_offset < SOURCE_TILE_SIZE;
             source_offset += blockDim.x) {
            if (source_offset < tile_count) {
                const int source_index = tile_start + source_offset;
                source_x[source_offset] = in[source_index].x;
                source_y[source_offset] = in[source_index].y;
                source_z[source_offset] = in[source_index].z;
                source_mass[source_offset] = in[source_index].mass;
            } else {
                source_x[source_offset] = 0.0f;
                source_y[source_offset] = 0.0f;
                source_z[source_offset] = 0.0f;
                source_mass[source_offset] = 0.0f;
            }
        }

        __syncthreads();

        if (valid_target) {
            for (int k = 0; k < tile_count; k++) {
                const int j = tile_start + k;
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

    if (valid_target) {
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
