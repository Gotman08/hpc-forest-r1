/*
  Copyright (c) 2010-2023, Intel Corporation

  SPDX-License-Identifier: BSD-3-Clause
*/

static void stencil_step(int x0, int x1, int y0, int y1, int z0, int z1, int Nx, int Ny, int Nz, const float coef[4],
                         const float vsq[], const float Ain[], float Aout[]) {
    int Nxy = Nx * Ny;

    for (int z = z0; z < z1; ++z) {
        for (int y = y0; y < y1; ++y) {
            int row = z * Nxy + y * Nx;
            const float* center = Ain + row;
            const float* ym1 = center - Nx;
            const float* yp1 = center + Nx;
            const float* ym2 = center - 2 * Nx;
            const float* yp2 = center + 2 * Nx;
            const float* ym3 = center - 3 * Nx;
            const float* yp3 = center + 3 * Nx;
            const float* zm1 = center - Nxy;
            const float* zp1 = center + Nxy;
            const float* zm2 = center - 2 * Nxy;
            const float* zp2 = center + 2 * Nxy;
            const float* zm3 = center - 3 * Nxy;
            const float* zp3 = center + 3 * Nxy;
            const float* velocity = vsq + row;
            float* dst = Aout + row;

#if defined(_OPENMP) && _OPENMP >= 201307
#pragma omp simd
#endif
            for (int x = x0; x < x1; ++x) {
                float div = coef[0] * center[x] +
                            coef[1] * (center[x + 1] + center[x - 1] + yp1[x] + ym1[x] + zp1[x] + zm1[x]) +
                            coef[2] * (center[x + 2] + center[x - 2] + yp2[x] + ym2[x] + zp2[x] + zm2[x]) +
                            coef[3] * (center[x + 3] + center[x - 3] + yp3[x] + ym3[x] + zp3[x] + zm3[x]);

                dst[x] = 2 * center[x] - dst[x] + velocity[x] * div;
            }
        }
    }
}

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
