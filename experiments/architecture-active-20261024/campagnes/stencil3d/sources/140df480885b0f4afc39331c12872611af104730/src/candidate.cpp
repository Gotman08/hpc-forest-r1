/*
  Copyright (c) 2010-2023, Intel Corporation

  SPDX-License-Identifier: BSD-3-Clause
*/

static void stencil_step(int x0, int x1, int y0, int y1, int z0, int z1, int Nx, int Ny, int Nz, const float coef[4],
                         const float vsq[], const float Ain[], float Aout[]) {
    const int Nxy = Nx * Ny;

    for (int z = z0; z < z1; ++z) {
        const int zbase = z * Nxy;
        for (int y = y0; y < y1; ++y) {
            const int row = zbase + y * Nx;
            const float* const in_row = Ain + row;
            const float* const vsq_row = vsq + row;
            float* const out_row = Aout + row;
            if (x0 >= x1)
                continue;

            const int width = x1 - x0;
            const float* in = in_row + x0;
            const float* vsq_x = vsq_row + x0;
            float* out = out_row + x0;
            for (int i = 0; i < width; ++i, ++in, ++vsq_x, ++out) {
                const float center = *in;
                const float div = coef[0] * center +
                                  coef[1] * (in[1] + in[-1] + in[Nx] + in[-Nx] + in[Nxy] + in[-Nxy]) +
                                  coef[2] * (in[2] + in[-2] + in[2 * Nx] + in[-2 * Nx] + in[2 * Nxy] + in[-2 * Nxy]) +
                                  coef[3] * (in[3] + in[-3] + in[3 * Nx] + in[-3 * Nx] + in[3 * Nxy] + in[-3 * Nxy]);

                *out = 2 * center - *out + *vsq_x * div;
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
extern "C" void run(const void* input1,const void* input2,void* output,int n,int parameter,int threads)
{size_t s=size_t(n)*n*n;const float*a=(const float*)input1;float*c=(float*)output;memcpy(c,a,s*4);memset(c+s,0,s*4);const float co[4]={.5f,-.25f,.125f,-.0625f};loop_stencil_serial(0,6,4,n-4,4,n-4,4,n-4,n,n,n,co,(const float*)input2,c,c+s);}
