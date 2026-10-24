/*
  Copyright (c) 2010-2023, Intel Corporation

  SPDX-License-Identifier: BSD-3-Clause
*/

#if defined(__GNUC__) || defined(__clang__)
#define STENCIL_RESTRICT __restrict__
#elif defined(_MSC_VER)
#define STENCIL_RESTRICT __restrict
#else
#define STENCIL_RESTRICT
#endif

static void stencil_step(int x0, int x1, int y0, int y1, int z0, int z1, int Nx, int Ny, int Nz, const float coef[4],
                         const float vsq[], const float Ain[], float* STENCIL_RESTRICT Aout) {
    int Nxy = Nx * Ny;

    for (int z = z0; z < z1; ++z) {
        for (int y = y0; y < y1; ++y) {
            int row = z * Nxy + y * Nx + x0;
            const float* center = Ain + row;
            const float* y_m1 = center - Nx;
            const float* y_p1 = center + Nx;
            const float* y_m2 = center - 2 * Nx;
            const float* y_p2 = center + 2 * Nx;
            const float* y_m3 = center - 3 * Nx;
            const float* y_p3 = center + 3 * Nx;
            const float* z_m1 = center - Nxy;
            const float* z_p1 = center + Nxy;
            const float* z_m2 = center - 2 * Nxy;
            const float* z_p2 = center + 2 * Nxy;
            const float* z_m3 = center - 3 * Nxy;
            const float* z_p3 = center + 3 * Nxy;
            const float* velocity = vsq + row;
            float* output = Aout + row;
            int width = x1 - x0;

            for (int i = 0; i < width; ++i) {
                float div = coef[0] * center[i] +
                            coef[1] * (center[i + 1] + center[i - 1] + y_p1[i] + y_m1[i] + z_p1[i] + z_m1[i]) +
                            coef[2] * (center[i + 2] + center[i - 2] + y_p2[i] + y_m2[i] + z_p2[i] + z_m2[i]) +
                            coef[3] * (center[i + 3] + center[i - 3] + y_p3[i] + y_m3[i] + z_p3[i] + z_m3[i]);

                output[i] = 2 * center[i] - output[i] + velocity[i] * div;
            }
        }
    }
}

#undef STENCIL_RESTRICT

void loop_stencil_serial(int t0, int t1, int x0, int x1, int y0, int y1, int z0, int z1, int Nx, int Ny, int Nz,
                         const float coef[4], const float vsq[], float Aeven[], float Aodd[]) {
    for (int t = t0; t < t1; ++t) {
        if ((t & 1) == 0)
            stencil_step(x0, x1, y0, y1, z0, z1, Nx, Ny, Nz, coef, vsq, Aeven, Aodd);
        else
            stencil_step(x0, x1, y0, y1, z0, z1, Nx, Ny, Nz, coef, vsq, Aodd, Aeven);
    }
}
#include <cstdint>
#include <cstring>
#include <cmath>
#include <algorithm>
#include <omp.h>
extern "C" void run(const void* input1,const void* input2,void* output,int n,int parameter,int threads)
{size_t s=size_t(n)*n*n;const float*a=(const float*)input1;float*c=(float*)output;memcpy(c,a,s*4);memset(c+s,0,s*4);const float co[4]={.5f,-.25f,.125f,-.0625f};loop_stencil_serial(0,6,4,n-4,4,n-4,4,n-4,n,n,n,co,(const float*)input2,c,c+s);}
