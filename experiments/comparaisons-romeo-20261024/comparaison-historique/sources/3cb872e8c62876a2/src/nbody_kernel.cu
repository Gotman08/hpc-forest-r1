// Structure AoS des particules.
struct Particle {
    float x, y, z;
    float vx, vy, vz;
    float mass;
};

// Chaque thread traite deux cibles adjacentes en gardant leurs accumulateurs
// en registres. Pour chaque source j, ses données sont chargées une fois puis
// réutilisées pour les deux calculs. Aucun tuilage en mémoire partagée.
extern "C" __global__ void nbody_step_naive(const Particle* in, Particle* out, int n, float dt) {
    const float G = 1.0f;
    const float softening = 0.001f;

    const long long first =
        (static_cast<long long>(blockIdx.x) * blockDim.x + threadIdx.x) * 2LL;
    const long long stride =
        static_cast<long long>(gridDim.x) * blockDim.x * 2LL;

    // Le stride couvre des paires successives jusqu'à n, y compris la queue
    // impaire, sans dépendre d'un rapport particulier entre n et le lancement.
    for (long long first_i = first; first_i < n; first_i += stride) {
        const int i0 = static_cast<int>(first_i);
        const int i1 = i0 + 1;
        const bool has1 = first_i + 1 < n;

        Particle p0 = in[i0];
        Particle p1;
        if (has1) p1 = in[i1];

        float fx0 = 0.0f;
        float fy0 = 0.0f;
        float fz0 = 0.0f;
        float fx1 = 0.0f;
        float fy1 = 0.0f;
        float fz1 = 0.0f;

        for (int j = 0; j < n; ++j) {
            const Particle source = in[j];

            if (j != i0) {
                const float dx = source.x - p0.x;
                const float dy = source.y - p0.y;
                const float dz = source.z - p0.z;

                const float distSq = dx * dx + dy * dy + dz * dz + softening;
                const float dist = sqrtf(distSq);
                const float f = (G * p0.mass * source.mass) / (distSq * dist);

                fx0 += f * dx;
                fy0 += f * dy;
                fz0 += f * dz;
            }

            if (has1 && j != i1) {
                const float dx = source.x - p1.x;
                const float dy = source.y - p1.y;
                const float dz = source.z - p1.z;

                const float distSq = dx * dx + dy * dy + dz * dz + softening;
                const float dist = sqrtf(distSq);
                const float f = (G * p1.mass * source.mass) / (distSq * dist);

                fx1 += f * dx;
                fy1 += f * dy;
                fz1 += f * dz;
            }
        }

        p0.vx += (fx0 / p0.mass) * dt;
        p0.vy += (fy0 / p0.mass) * dt;
        p0.vz += (fz0 / p0.mass) * dt;
        p0.x += p0.vx * dt;
        p0.y += p0.vy * dt;
        p0.z += p0.vz * dt;
        out[i0] = p0;

        if (has1) {
            p1.vx += (fx1 / p1.mass) * dt;
            p1.vy += (fy1 / p1.mass) * dt;
            p1.vz += (fz1 / p1.mass) * dt;
            p1.x += p1.vx * dt;
            p1.y += p1.vy * dt;
            p1.z += p1.vz * dt;
            out[i1] = p1;
        }
    }
}
