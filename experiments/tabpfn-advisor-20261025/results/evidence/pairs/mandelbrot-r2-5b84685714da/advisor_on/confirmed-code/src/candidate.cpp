/*
  Copyright (c) 2010-2023, Intel Corporation

  SPDX-License-Identifier: BSD-3-Clause
*/

#include <cstdint>
#include <cstring>
#include <cmath>
#include <algorithm>
#include <omp.h>

static int mandel(float c_re, float c_im, int count) {
    float z_re = c_re, z_im = c_im;
    float checkpoint_re = 0.f, checkpoint_im = 0.f;
    std::uint64_t checkpoint_power = 1;
    std::uint64_t checkpoint_distance = 0;
    int i;
    for (i = 0; i < count; ++i) {
        if (z_re * z_re + z_im * z_im > 4.f)
            break;

        // Sample Brent's checkpoint logic every 8 iterations, after the escape test.
        if ((i & 7) == 0) {
            if (i == 0) {
                checkpoint_re = z_re;
                checkpoint_im = z_im;
            } else {
                ++checkpoint_distance;
                if (std::memcmp(&z_re, &checkpoint_re, sizeof(float)) == 0 &&
                    std::memcmp(&z_im, &checkpoint_im, sizeof(float)) == 0)
                    return count;

                if (checkpoint_distance == checkpoint_power) {
                    checkpoint_re = z_re;
                    checkpoint_im = z_im;
                    checkpoint_power <<= 1;
                    checkpoint_distance = 0;
                }
            }
        }

        float new_re = z_re * z_re - z_im * z_im;
        float new_im = 2.f * z_re * z_im;
        z_re = c_re + new_re;
        z_im = c_im + new_im;
    }

    return i;
}

// Interleave four adjacent scalar recurrences so the compiler can SLP-vectorize
// their identical arithmetic while each lane retains its own exact cycle test.
static void mandel4(float c0, float c1, float c2, float c3, float c_im,
                    int count, int output[4]) {
    float z_re0 = c0, z_im0 = c_im;
    float z_re1 = c1, z_im1 = c_im;
    float z_re2 = c2, z_im2 = c_im;
    float z_re3 = c3, z_im3 = c_im;

    float checkpoint_re0 = z_re0, checkpoint_im0 = z_im0;
    float checkpoint_re1 = z_re1, checkpoint_im1 = z_im1;
    float checkpoint_re2 = z_re2, checkpoint_im2 = z_im2;
    float checkpoint_re3 = z_re3, checkpoint_im3 = z_im3;
    std::uint64_t checkpoint_power0 = 1, checkpoint_distance0 = 0;
    std::uint64_t checkpoint_power1 = 1, checkpoint_distance1 = 0;
    std::uint64_t checkpoint_power2 = 1, checkpoint_distance2 = 0;
    std::uint64_t checkpoint_power3 = 1, checkpoint_distance3 = 0;

    int iterations0 = count > 0 ? count : 0;
    int iterations1 = count > 0 ? count : 0;
    int iterations2 = count > 0 ? count : 0;
    int iterations3 = count > 0 ? count : 0;
    bool active0 = count > 0, active1 = count > 0;
    bool active2 = count > 0, active3 = count > 0;

    for (int iter = 0; iter < count; ++iter) {
        if (active0 && z_re0 * z_re0 + z_im0 * z_im0 > 4.f) {
            iterations0 = iter;
            active0 = false;
        }
        if (active1 && z_re1 * z_re1 + z_im1 * z_im1 > 4.f) {
            iterations1 = iter;
            active1 = false;
        }
        if (active2 && z_re2 * z_re2 + z_im2 * z_im2 > 4.f) {
            iterations2 = iter;
            active2 = false;
        }
        if (active3 && z_re3 * z_re3 + z_im3 * z_im3 > 4.f) {
            iterations3 = iter;
            active3 = false;
        }

        if (!(active0 || active1 || active2 || active3))
            break;

        if (iter != 0 && (iter & 7) == 0) {
            if (active0) {
                ++checkpoint_distance0;
                if (std::memcmp(&z_re0, &checkpoint_re0, sizeof(float)) == 0 &&
                    std::memcmp(&z_im0, &checkpoint_im0, sizeof(float)) == 0) {
                    iterations0 = count;
                    active0 = false;
                } else if (checkpoint_distance0 == checkpoint_power0) {
                    checkpoint_re0 = z_re0;
                    checkpoint_im0 = z_im0;
                    checkpoint_power0 <<= 1;
                    checkpoint_distance0 = 0;
                }
            }
            if (active1) {
                ++checkpoint_distance1;
                if (std::memcmp(&z_re1, &checkpoint_re1, sizeof(float)) == 0 &&
                    std::memcmp(&z_im1, &checkpoint_im1, sizeof(float)) == 0) {
                    iterations1 = count;
                    active1 = false;
                } else if (checkpoint_distance1 == checkpoint_power1) {
                    checkpoint_re1 = z_re1;
                    checkpoint_im1 = z_im1;
                    checkpoint_power1 <<= 1;
                    checkpoint_distance1 = 0;
                }
            }
            if (active2) {
                ++checkpoint_distance2;
                if (std::memcmp(&z_re2, &checkpoint_re2, sizeof(float)) == 0 &&
                    std::memcmp(&z_im2, &checkpoint_im2, sizeof(float)) == 0) {
                    iterations2 = count;
                    active2 = false;
                } else if (checkpoint_distance2 == checkpoint_power2) {
                    checkpoint_re2 = z_re2;
                    checkpoint_im2 = z_im2;
                    checkpoint_power2 <<= 1;
                    checkpoint_distance2 = 0;
                }
            }
            if (active3) {
                ++checkpoint_distance3;
                if (std::memcmp(&z_re3, &checkpoint_re3, sizeof(float)) == 0 &&
                    std::memcmp(&z_im3, &checkpoint_im3, sizeof(float)) == 0) {
                    iterations3 = count;
                    active3 = false;
                } else if (checkpoint_distance3 == checkpoint_power3) {
                    checkpoint_re3 = z_re3;
                    checkpoint_im3 = z_im3;
                    checkpoint_power3 <<= 1;
                    checkpoint_distance3 = 0;
                }
            }
        }

        float new_re0 = z_re0 * z_re0 - z_im0 * z_im0;
        float new_im0 = 2.f * z_re0 * z_im0;
        z_re0 = c0 + new_re0;
        z_im0 = c_im + new_im0;

        float new_re1 = z_re1 * z_re1 - z_im1 * z_im1;
        float new_im1 = 2.f * z_re1 * z_im1;
        z_re1 = c1 + new_re1;
        z_im1 = c_im + new_im1;

        float new_re2 = z_re2 * z_re2 - z_im2 * z_im2;
        float new_im2 = 2.f * z_re2 * z_im2;
        z_re2 = c2 + new_re2;
        z_im2 = c_im + new_im2;

        float new_re3 = z_re3 * z_re3 - z_im3 * z_im3;
        float new_im3 = 2.f * z_re3 * z_im3;
        z_re3 = c3 + new_re3;
        z_im3 = c_im + new_im3;
    }

    output[0] = iterations0;
    output[1] = iterations1;
    output[2] = iterations2;
    output[3] = iterations3;
}

void mandelbrot_serial(float x0, float y0, float x1, float y1, int width,
                       int height, int maxIterations, int output[], int threads) {
    float dx = (x1 - x0) / width;
    float dy = (y1 - y0) / height;
    int thread_count = threads > 0 ? threads : 1;
    int vector_end = width > 0 ? width - width % 4 : 0;

    #pragma omp parallel for schedule(dynamic, 4) num_threads(thread_count) if(thread_count > 1)
    for (int j = 0; j < height; ++j) {
        float y = y0 + j * dy;
        int i = 0;
        for (; i < vector_end; i += 4) {
            float c0 = x0 + i * dx;
            float c1 = x0 + (i + 1) * dx;
            float c2 = x0 + (i + 2) * dx;
            float c3 = x0 + (i + 3) * dx;
            int counts[4];
            mandel4(c0, c1, c2, c3, y, maxIterations, counts);

            int index = j * width + i;
            output[index] = counts[0];
            output[index + 1] = counts[1];
            output[index + 2] = counts[2];
            output[index + 3] = counts[3];
        }
        for (; i < width; ++i) {
            float x = x0 + i * dx;
            int index = j * width + i;
            output[index] = mandel(x, y, maxIterations);
        }
    }
}

extern "C" void run(const void* input1, const void* input2, void* output,
                    int n, int parameter, int threads) {
    const float* a = static_cast<const float*>(input1);
    mandelbrot_serial(a[0], a[1], a[2], a[3], n * 3 / 2, n, parameter,
                      static_cast<int*>(output), threads);
}
