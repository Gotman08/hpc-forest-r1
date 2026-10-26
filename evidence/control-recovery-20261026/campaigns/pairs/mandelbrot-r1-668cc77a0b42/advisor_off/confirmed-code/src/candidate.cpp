/*
  Copyright (c) 2010-2023, Intel Corporation

  SPDX-License-Identifier: BSD-3-Clause
*/

#include <cstdint>
#include <cstring>
#include <cmath>
#include <algorithm>
#include <omp.h>

static bool same_float_bits(float a, float b) {
    return std::memcmp(&a, &b, sizeof(float)) == 0;
}

static bool in_parameter_disk(float c_re, float c_im,
                              double center_re, double center_im,
                              double radius) {
    const double dx = static_cast<double>(c_re) - center_re;
    const double dy = static_cast<double>(c_im) - center_im;
    // An inward allowance well above binary64 comparison roundoff for these
    // binary32 inputs keeps the parameter test conservative at its boundary.
    const double comparison_slack = 9.094947017729282e-13; // 2^-40
    return dx * dx + dy * dy <= radius * radius - comparison_slack;
}

static bool certifies_non_escape(float c_re, float c_im) {
    // For the update below, while |z| <= 1.15 and |c| <= 1.026, a
    // conservative Euclidean bound for binary32 rounding is 2^-20. It covers
    // the products, subtraction and addition (including subnormal terms).
    const double step_error = 9.5367431640625e-7; // 2^-20

    if (in_parameter_disk(c_re, c_im, 0.0, 0.0, 0.249)) {
        // Starting at z=c gives |z|<=0.249. Thereafter
        // |z*z+c|<=0.249+0.5^2, with ample room for step_error, so |z|<=0.5.
        return 0.249 + 0.5 * 0.5 + step_error < 0.5;
    }

    if (in_parameter_disk(c_re, c_im, -0.3125, 0.0, 0.04)) {
        // p=-1/4 is an exactly representable fixed point for c0=-5/16.
        // With delta=c-c0 and e=z-p, F_c(z)-p=-e/2+e*e+delta.
        // Initially |e|<=1/16+0.04<1/8; the next bound is
        // 1/16+1/64+0.04+step_error<1/8, hence the orbit stays near p.
        return 1.0 / 16.0 + 1.0 / 64.0 + 0.04 + step_error < 1.0 / 8.0;
    }

    if (in_parameter_disk(c_re, c_im, -1.0, 0.0, 0.026)) {
        // Let delta=c+1. Starting at z=c gives |z+1|<=0.026<0.15.
        // The alternating disks |z+1|<=0.15 and |z|<=0.35 map into each
        // other: 2*0.15+0.15^2+0.026+error<0.35 and
        // 0.35^2+0.026+error<0.15. Both disks are inside |z|<2.
        return 2.0 * 0.15 + 0.15 * 0.15 + 0.026 + step_error < 0.35 &&
               0.35 * 0.35 + 0.026 + step_error < 0.15;
    }

    return false;
}

static int mandel(float c_re, float c_im, int count) {
    if (count > 0 && certifies_non_escape(c_re, c_im))
        return count;

    float z_re = c_re, z_im = c_im;
    float checkpoint_re = 0.0f, checkpoint_im = 0.0f;
    std::uint64_t power = 1, distance = 0;
    bool have_checkpoint = false;
    int i;

    for (i = 0; i < count; ++i) {
        if (z_re * z_re + z_im * z_im > 4.f)
            break;

        if (std::isfinite(z_re) && std::isfinite(z_im)) {
            if (!have_checkpoint) {
                checkpoint_re = z_re;
                checkpoint_im = z_im;
                power = 1;
                distance = 0;
                have_checkpoint = true;
            } else {
                if (same_float_bits(z_re, checkpoint_re) &&
                    same_float_bits(z_im, checkpoint_im))
                    return count;

                ++distance;
                if (distance == power) {
                    checkpoint_re = z_re;
                    checkpoint_im = z_im;
                    if (power <= UINT64_MAX / 2)
                        power *= 2;
                    distance = 0;
                }
            }
        } else {
            have_checkpoint = false;
            power = 1;
            distance = 0;
        }

        float new_re = z_re * z_re - z_im * z_im;
        float new_im = 2.f * z_re * z_im;
        float next_re = c_re + new_re;
        float next_im = c_im + new_im;
        z_re = next_re;
        z_im = next_im;
    }

    return i;
}

void mandelbrot_serial(float x0, float y0, float x1, float y1, int width, int height, int maxIterations, int output[]) {
    float dx = (x1 - x0) / width;
    float dy = (y1 - y0) / height;

    for (int j = 0; j < height; j++) {
        for (int i = 0; i < width; ++i) {
            float x = x0 + i * dx;
            float y = y0 + j * dy;

            int index = (j * width + i);
            output[index] = mandel(x, y, maxIterations);
        }
    }
}

static void mandelbrot_interleaved_static(float x0, float y0, float x1,
                                          float y1, int width, int height,
                                          int maxIterations, int output[],
                                          int threads) {
    float dx = (x1 - x0) / width;
    float dy = (y1 - y0) / height;

    #pragma omp parallel for schedule(static, 1) num_threads(threads)
    for (int j = 0; j < height; ++j) {
        float y = y0 + j * dy;
        for (int i = 0; i < width; ++i) {
            float x = x0 + i * dx;
            int index = j * width + i;
            output[index] = mandel(x, y, maxIterations);
        }
    }
}

extern "C" void run(const void* input1, const void* input2, void* output,
                     int n, int parameter, int threads) {
    const float* a = static_cast<const float*>(input1);
    const int width = n * 3 / 2;
    const int height = n;
    int* result = static_cast<int*>(output);

    if (threads <= 1) {
        mandelbrot_serial(a[0], a[1], a[2], a[3], width, height, parameter,
                          result);
    } else {
        mandelbrot_interleaved_static(a[0], a[1], a[2], a[3], width, height,
                                      parameter, result, threads);
    }
}
