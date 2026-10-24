// Structure "Array of Structures" (AoS).
struct Particle {
    float x, y, z;
    float vx, vy, vz;
    float mass;
};

// Keep these aligned with launch.json: block=256, items_per_block=8.
static constexpr int kWarpSize = 32;
static constexpr int kOutputsPerBlock = 8;

// One warp cooperates on each target; the configured grid covers ceil(n / 8) targets per block.
extern "C" __global__ void nbody_step_naive(const Particle* in, Particle* out, int n, float dt) {
    const int lane = threadIdx.x % kWarpSize;
    const int warp_in_block = threadIdx.x / kWarpSize;
    const int i = blockIdx.x * kOutputsPerBlock + warp_in_block;
    if (i >= n) return;

    const float G = 1.0f;
    const float softening = 0.001f;

    float fx = 0.0f;
    float fy = 0.0f;
    float fz = 0.0f;

    // Lanes partition the source indices while retaining the baseline force expression.
    for (int j = lane; j < n;) {
        if (i != j) {
            float dx = in[j].x - in[i].x;
            float dy = in[j].y - in[i].y;
            float dz = in[j].z - in[i].z;

            float distSq = dx * dx + dy * dy + dz * dz + softening;
            float dist = sqrtf(distSq);

            float f = (G * in[i].mass * in[j].mass) / (distSq * dist);

            fx += f * dx;
            fy += f * dy;
            fz += f * dz;
        }

        // Avoid overflowing j when n is near the largest positive int.
        if (n - j <= kWarpSize) break;
        j += kWarpSize;
    }

    // All lanes in each valid warp participate in every shuffle; lane zero owns the output.
    const unsigned int warp_mask = 0xffffffffu;
    for (int offset = kWarpSize / 2; offset > 0; offset >>= 1) {
        fx += __shfl_down_sync(warp_mask, fx, offset);
        fy += __shfl_down_sync(warp_mask, fy, offset);
        fz += __shfl_down_sync(warp_mask, fz, offset);
    }

    if (lane != 0) return;

    // Integrate once per target.
    Particle p = in[i];
    p.vx += (fx / p.mass) * dt;
    p.vy += (fy / p.mass) * dt;
    p.vz += (fz / p.mass) * dt;

    p.x += p.vx * dt;
    p.y += p.vy * dt;
    p.z += p.vz * dt;

    out[i] = p;
}
