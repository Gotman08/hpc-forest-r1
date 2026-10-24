struct Particle {
    float x, y, z;
    float vx, vy, vz;
    float mass;
};

extern "C" __global__ void nbody_step_naive(const Particle* in, Particle* out, int n, float dt) {
    constexpr int kSourceTile = 2048;

    extern __shared__ float shared[];
    float* tileX = shared;
    float* tileY = tileX + kSourceTile;
    float* tileZ = tileY + kSourceTile;
    float* tileMass = tileZ + kSourceTile;

    const int lane = threadIdx.x & 31;
    const int warps_per_block = blockDim.x / 32;
    const int warp_in_block = threadIdx.x / 32;
    const int i = blockIdx.x * warps_per_block + warp_in_block;

    const float G = 1.0f;
    const float softening = 0.001f;

    float target_x = 0.0f;
    float target_y = 0.0f;
    float target_z = 0.0f;
    float target_mass = 0.0f;
    if (i < n) {
        target_x = in[i].x;
        target_y = in[i].y;
        target_z = in[i].z;
        target_mass = in[i].mass;
    }

    float fx = 0.0f;
    float fy = 0.0f;
    float fz = 0.0f;

    for (int tileStart = 0; tileStart < n;) {
        const int remaining = n - tileStart;
        const int tileCount = remaining < kSourceTile ? remaining : kSourceTile;

        for (int k = threadIdx.x; k < tileCount; k += blockDim.x) {
            const int sourceIndex = tileStart + k;
            tileX[k] = in[sourceIndex].x;
            tileY[k] = in[sourceIndex].y;
            tileZ[k] = in[sourceIndex].z;
            tileMass[k] = in[sourceIndex].mass;
        }
        __syncthreads();

        if (i < n) {
            for (int k = lane; k < tileCount; k += 32) {
                const int j = tileStart + k;
                if (i == j) continue;

                const float dx = tileX[k] - target_x;
                const float dy = tileY[k] - target_y;
                const float dz = tileZ[k] - target_z;

                const float distSq = dx * dx + dy * dy + dz * dz + softening;
                const float invDist = rsqrtf(distSq);
                const float invDistCubed = (invDist * invDist) * invDist;
                const float f = (G * target_mass * tileMass[k]) * invDistCubed;

                fx += f * dx;
                fy += f * dy;
                fz += f * dz;
            }
        }
        __syncthreads();
        tileStart += tileCount;
    }

    const unsigned int full_warp_mask = 0xffffffffu;
    for (int offset = 16; offset > 0; offset >>= 1) {
        fx += __shfl_down_sync(full_warp_mask, fx, offset);
        fy += __shfl_down_sync(full_warp_mask, fy, offset);
        fz += __shfl_down_sync(full_warp_mask, fz, offset);
    }

    if (lane == 0 && i < n) {
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
