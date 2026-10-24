/*
  Copyright (c) 2010-2023, Intel Corporation

  SPDX-License-Identifier: BSD-3-Clause
*/

static void stencil_step(int x0, int x1, int y0, int y1, int z0, int z1, int Nx, int Ny, int Nz, const float coef[4],
                         const float vsq[], const float Ain[], float Aout[]) {
    int Nxy = Nx * Ny;
    int row_length = x1 - x0;

    for (int z = z0; z < z1; ++z) {
        for (int y = y0; y < y1; ++y) {
            int row_start = z * Nxy + y * Nx + x0;
            const float* in_line = Ain + row_start;
            const float* vsq_line = vsq + row_start;
            float* out_line = Aout + row_start;

#if defined(_OPENMP) && _OPENMP >= 201307
#pragma omp simd
#endif
            for (int ix = 0; ix < row_length; ++ix) {
                float center = in_line[ix];
                float div = coef[0] * center +
                            coef[1] * (in_line[ix + 1] + in_line[ix - 1] + in_line[ix + Nx] + in_line[ix - Nx] +
                                       in_line[ix + Nxy] + in_line[ix - Nxy]) +
                            coef[2] * (in_line[ix + 2] + in_line[ix - 2] + in_line[ix + 2 * Nx] + in_line[ix - 2 * Nx] +
                                       in_line[ix + 2 * Nxy] + in_line[ix - 2 * Nxy]) +
                            coef[3] * (in_line[ix + 3] + in_line[ix - 3] + in_line[ix + 3 * Nx] + in_line[ix - 3 * Nx] +
                                       in_line[ix + 3 * Nxy] + in_line[ix - 3 * Nxy]);

                out_line[ix] = 2 * center - out_line[ix] + vsq_line[ix] * div;
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
