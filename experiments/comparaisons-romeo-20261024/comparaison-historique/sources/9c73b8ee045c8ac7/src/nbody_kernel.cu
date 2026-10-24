// Array-of-structures particle layout shared by the host and kernel.
struct Particle {
    float x, y, z;
    float vx, vy, vz;
    float mass;
};

// Each thread updates one target. Blocks cooperatively stage source tiles in
// dynamic shared memory, while each target traverses sources in index order.
extern "C" __global__ void nbody_step_naive(const Particle* in, Particle* out, int n, float dt) {
    const int lane = threadIdx.x;
    const int i = blockIdx.x * blockDim.x + lane;
    const bool active = i < n;
    extern __shared__ Particle source_tile[];

    Particle target;
    if (active) {
        target = in[i];
    }

    const float G = 1.0f;
    const float softening = 0.001f;
    float fx = 0.0f;
    float fy = 0.0f;
    float fz = 0.0f;

    const int source_tile_size = 256;
    for (int base = 0; base < n;) {
        const int remaining = n - base;
        const int tile_count = remaining < source_tile_size ? remaining : source_tile_size;

        // A 128-thread block loads up to two source particles per lane.
        const int second_offset = lane + blockDim.x;
        if (lane < tile_count) {
            source_tile[lane] = in[base + lane];
        }
        if (second_offset < tile_count) {
            source_tile[second_offset] = in[base + second_offset];
        }
        __syncthreads();

        if (active) {
            for (int k = 0; k < tile_count; ++k) {
                const int j = base + k;
                if (i == j) continue;

                const Particle source = source_tile[k];
                const float dx = source.x - target.x;
                const float dy = source.y - target.y;
                const float dz = source.z - target.z;

                const float distSq = dx * dx + dy * dy + dz * dz + softening;
                const float dist = sqrtf(distSq);
                const float f = (G * target.mass * source.mass) / (distSq * dist);

                fx += f * dx;
                fy += f * dy;
                fz += f * dz;
            }
        }

        // Inactive target threads also reach both barriers before a tile is reused.
        __syncthreads();
        base += tile_count;
    }

    if (active) {
        target.vx += (fx / target.mass) * dt;
        target.vy += (fy / target.mass) * dt;
        target.vz += (fz / target.mass) * dt;

        target.x += target.vx * dt;
        target.y += target.vy * dt;
        target.z += target.vz * dt;

        out[i] = target;
    }
}
