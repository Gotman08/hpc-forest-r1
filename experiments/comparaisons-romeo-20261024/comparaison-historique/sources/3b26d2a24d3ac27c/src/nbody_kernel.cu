struct Particle {
    float x, y, z;
    float vx, vy, vz;
    float mass;
};

extern "C" __global__ void nbody_step_naive(const Particle* in, Particle* out, int n, float dt) {
    const int tid = threadIdx.x;
    const int stride = blockDim.x;
    const int i = static_cast<int>(blockIdx.x);
    if (i >= n) return;

    const float G = 1.0f;
    const float softening = 0.001f;

    __shared__ Particle target;
    __shared__ float partial_fx[256];
    __shared__ float partial_fy[256];
    __shared__ float partial_fz[256];

    if (tid == 0) target = in[i];
    __syncthreads();

    float fx = 0.0f;
    float fy = 0.0f;
    float fz = 0.0f;

    for (int j = tid; j < n;) {
        if (j != i) {
            float dx = in[j].x - target.x;
            float dy = in[j].y - target.y;
            float dz = in[j].z - target.z;

            float distSq = dx * dx + dy * dy + dz * dz + softening;
            float dist = sqrtf(distSq);
            float f = (G * target.mass * in[j].mass) / (distSq * dist);

            fx += f * dx;
            fy += f * dy;
            fz += f * dz;
        }
        if (n - j <= stride) break;
        j += stride;
    }

    partial_fx[tid] = fx;
    partial_fy[tid] = fy;
    partial_fz[tid] = fz;
    __syncthreads();

    for (int offset = stride >> 1; offset > 0; offset >>= 1) {
        if (tid < offset) {
            partial_fx[tid] += partial_fx[tid + offset];
            partial_fy[tid] += partial_fy[tid + offset];
            partial_fz[tid] += partial_fz[tid + offset];
        }
        __syncthreads();
    }

    if (tid == 0) {
        Particle p = target;
        p.vx += (partial_fx[0] / p.mass) * dt;
        p.vy += (partial_fy[0] / p.mass) * dt;
        p.vz += (partial_fz[0] / p.mass) * dt;

        p.x += p.vx * dt;
        p.y += p.vy * dt;
        p.z += p.vz * dt;

        out[i] = p;
    }
}
