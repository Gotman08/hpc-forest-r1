#include <cstdio>
#include <cstdlib>
#include <cmath>
#include <cuda_runtime.h>

// Structure "Array of Structures" (AoS) : intuitive mais naïve sur GPU
// car elle empêche la coalescence parfaite des accès mémoire.
struct Particle {
    float x, y, z;
    float vx, vy, vz;
    float mass;
};

// Kernel CUDA naïf : Simulation gravitationnelle N-Corps (N-Body)
__global__ void nbody_step_naive(const Particle* in, Particle* out, int n, float dt) {
    int i = blockIdx.x * blockDim.x + threadIdx.x;
    if (i >= n) return;

    const float G = 1.0f;
    const float softening = 0.001f;

    float fx = 0.0f;
    float fy = 0.0f;
    float fz = 0.0f;

    // Approche naïve : chaque thread parcourt toutes les particules en mémoire globale
    // sans utiliser de mémoire partagée (__shared__) ni mettre in[i] en registre.
    for (int j = 0; j < n; j++) {
        if (i == j) continue; // Divergence de branche inutile dans la boucle

        float dx = in[j].x - in[i].x;
        float dy = in[j].y - in[i].y;
        float dz = in[j].z - in[i].z;

        float distSq = dx * dx + dy * dy + dz * dz + softening;
        float dist = sqrtf(distSq); // Calcul coûteux (au lieu de rsqrtf)

        float f = (G * in[i].mass * in[j].mass) / (distSq * dist);

        fx += f * dx;
        fy += f * dy;
        fz += f * dz;
    }

    // Intégration d'Euler explicite
    Particle p = in[i];
    p.vx += (fx / p.mass) * dt;
    p.vy += (fy / p.mass) * dt;
    p.vz += (fz / p.mass) * dt;

    p.x += p.vx * dt;
    p.y += p.vy * dt;
    p.z += p.vz * dt;

    out[i] = p;
}

int main() {
    const int N = 4096;
    const float dt = 0.01f;
    const size_t bytes = N * sizeof(Particle);

    // Allocation CPU
    Particle* h_particles = (Particle*)malloc(bytes);
    for (int i = 0; i < N; i++) {
        h_particles[i].x = (float)(rand() % 1000) / 100.0f;
        h_particles[i].y = (float)(rand() % 1000) / 100.0f;
        h_particles[i].z = (float)(rand() % 1000) / 100.0f;
        h_particles[i].vx = 0.0f;
        h_particles[i].vy = 0.0f;
        h_particles[i].vz = 0.0f;
        h_particles[i].mass = 1.0f + (float)(rand() % 100) / 10.0f;
    }

    // Allocation GPU
    Particle *d_in, *d_out;
    cudaMalloc(&d_in, bytes);
    cudaMalloc(&d_out, bytes);

    cudaMemcpy(d_in, h_particles, bytes, cudaMemcpyHostToDevice);

    // Configuration d'exécution simple
    int threadsPerBlock = 256;
    int blocksPerGrid = (N + threadsPerBlock - 1) / threadsPerBlock;

    printf("Lancement du kernel N-Body naif pour %d particules...\n", N);
    nbody_step_naive<<<blocksPerGrid, threadsPerBlock>>>(d_in, d_out, N, dt);
    cudaDeviceSynchronize();

    // Récupération des résultats
    cudaMemcpy(h_particles, d_out, bytes, cudaMemcpyDeviceToHost);

    printf("Exemple apres 1 pas de temps -> Particule 0 : pos=(%.3f, %.3f, %.3f), vel=(%.3f, %.3f, %.3f)\n",
           h_particles[0].x, h_particles[0].y, h_particles[0].z,
           h_particles[0].vx, h_particles[0].vy, h_particles[0].vz);

    cudaFree(d_in);
    cudaFree(d_out);
    free(h_particles);

    return 0;
}
