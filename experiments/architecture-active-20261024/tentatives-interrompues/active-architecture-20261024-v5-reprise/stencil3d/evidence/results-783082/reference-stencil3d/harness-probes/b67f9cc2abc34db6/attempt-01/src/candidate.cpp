/*
  Copyright (c) 2010-2023, Intel Corporation

  SPDX-License-Identifier: BSD-3-Clause
*/

#include <cstddef>
#include <cstring>
#include <omp.h>

using std::size_t;

static void stencil_row(int y, int z, int x0, int x1, int Nx, int Ny,
                        const float coef[4], const float vsq[],
                        const float Ain[], float Aout[]) {
    const int Nxy = Nx * Ny;
    const int row_base = z * Nxy + y * Nx;

    for (int x = x0; x < x1; ++x) {
        const int index = row_base + x;
#define A_cur(x, y, z) Ain[index + (x) + ((y) * Nx) + ((z) * Nxy)]
#define A_next(x, y, z) Aout[index + (x) + ((y) * Nx) + ((z) * Nxy)]
        const float div = coef[0] * A_cur(0, 0, 0) +
                          coef[1] * (A_cur(+1, 0, 0) + A_cur(-1, 0, 0) +
                                     A_cur(0, +1, 0) + A_cur(0, -1, 0) +
                                     A_cur(0, 0, +1) + A_cur(0, 0, -1)) +
                          coef[2] * (A_cur(+2, 0, 0) + A_cur(-2, 0, 0) +
                                     A_cur(0, +2, 0) + A_cur(0, -2, 0) +
                                     A_cur(0, 0, +2) + A_cur(0, 0, -2)) +
                          coef[3] * (A_cur(+3, 0, 0) + A_cur(-3, 0, 0) +
                                     A_cur(0, +3, 0) + A_cur(0, -3, 0) +
                                     A_cur(0, 0, +3) + A_cur(0, 0, -3));

        A_next(0, 0, 0) = 2 * A_cur(0, 0, 0) - A_next(0, 0, 0) +
                          vsq[index] * div;
#undef A_cur
#undef A_next
    }
}

static void stencil_step(int x0, int x1, int y0, int y1, int z0, int z1,
                         int Nx, int Ny, const float coef[4],
                         const float vsq[], const float Ain[], float Aout[]) {
    for (int z = z0; z < z1; ++z) {
        for (int y = y0; y < y1; ++y) {
            stencil_row(y, z, x0, x1, Nx, Ny, coef, vsq, Ain, Aout);
        }
    }
}

void loop_stencil_serial(int t0, int t1, int x0, int x1, int y0, int y1,
                         int z0, int z1, int Nx, int Ny, int Nz,
                         const float coef[4], const float vsq[],
                         float Aeven[], float Aodd[]) {
    (void)Nz;
    for (int t = t0; t < t1; ++t) {
        if ((t & 1) == 0) {
            stencil_step(x0, x1, y0, y1, z0, z1, Nx, Ny, coef, vsq,
                         Aeven, Aodd);
        } else {
            stencil_step(x0, x1, y0, y1, z0, z1, Nx, Ny, coef, vsq,
                         Aodd, Aeven);
        }
    }
}

struct RowRange {
    size_t first;
    size_t last;
};

// Assign contiguous row blocks explicitly, using the actual team size.
static RowRange static_row_range(size_t row_count, int thread_id,
                                 int team_size) {
    const size_t team = static_cast<size_t>(team_size);
    const size_t tid = static_cast<size_t>(thread_id);
    const size_t rows_per_thread = row_count / team;
    const size_t extra_rows = row_count % team;
    const size_t first = rows_per_thread * tid +
                         (tid < extra_rows ? tid : extra_rows);
    const size_t count = rows_per_thread + (tid < extra_rows ? 1 : 0);
    return RowRange{first, first + count};
}

static void stencil_rows(size_t first_row, size_t last_row,
                         int x0, int x1, int y0, int y1, int z0,
                         int Nx, int Ny, const float coef[4],
                         const float vsq[], const float Ain[], float Aout[]) {
    if (first_row == last_row) {
        return;
    }

    const int rows_per_plane = y1 - y0;
    if (rows_per_plane <= 0) {
        return;
    }

    const size_t plane_rows = static_cast<size_t>(rows_per_plane);
    int z = z0 + static_cast<int>(first_row / plane_rows);
    int y = y0 + static_cast<int>(first_row % plane_rows);

    for (size_t row = first_row; row < last_row; ++row) {
        stencil_row(y, z, x0, x1, Nx, Ny, coef, vsq, Ain, Aout);
        if (++y == y1) {
            y = y0;
            ++z;
        }
    }
}

static void loop_stencil_parallel_per_step(
    int t0, int t1, int x0, int x1, int y0, int y1, int z0, int z1,
    int Nx, int Ny, const float coef[4], const float vsq[],
    float Aeven[], float Aodd[], int threads) {
    const size_t row_count = static_cast<size_t>(y1 - y0) *
                             static_cast<size_t>(z1 - z0);

    for (int t = t0; t < t1; ++t) {
        const float *Ain = ((t & 1) == 0) ? Aeven : Aodd;
        float *Aout = ((t & 1) == 0) ? Aodd : Aeven;

#pragma omp parallel num_threads(threads) default(none) shared(x0, x1, y0, y1, z0, Nx, Ny, coef, vsq, Ain, Aout, row_count)
        {
            const RowRange range = static_row_range(
                row_count, omp_get_thread_num(), omp_get_num_threads());
            stencil_rows(range.first, range.last, x0, x1, y0, y1, z0,
                         Nx, Ny, coef, vsq, Ain, Aout);
        }
    }
}

extern "C" void run(const void *input1, const void *input2, void *output,
                     int n, int parameter, int threads) {
    (void)parameter;
    const size_t cells = static_cast<size_t>(n) *
                         static_cast<size_t>(n) * static_cast<size_t>(n);
    const float *input = static_cast<const float *>(input1);
    float *Aeven = static_cast<float *>(output);
    float *Aodd = Aeven + cells;

    std::memcpy(Aeven, input, cells * sizeof(float));
    std::memset(Aodd, 0, cells * sizeof(float));

    const float coef[4] = {0.5f, -0.25f, 0.125f, -0.0625f};
    const float *vsq = static_cast<const float *>(input2);
    const int x0 = 4;
    const int x1 = n - 4;
    const int y0 = 4;
    const int y1 = n - 4;
    const int z0 = 4;
    const int z1 = n - 4;

    const size_t inner_width = n > 8 ? static_cast<size_t>(n - 8) : 0;
    const size_t active_cells = inner_width * inner_width * inner_width;
    constexpr size_t serial_cutoff_cells = 32768;

    if (threads <= 0 || active_cells < serial_cutoff_cells) {
        loop_stencil_serial(0, 6, x0, x1, y0, y1, z0, z1,
                            n, n, n, coef, vsq, Aeven, Aodd);
    } else {
        // Recreate a team per timestep at every parallel thread budget.
        loop_stencil_parallel_per_step(0, 6, x0, x1, y0, y1, z0, z1,
                                       n, n, coef, vsq, Aeven, Aodd, threads);
    }
}
