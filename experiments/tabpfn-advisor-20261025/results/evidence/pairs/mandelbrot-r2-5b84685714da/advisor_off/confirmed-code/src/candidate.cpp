/*
  Copyright (c) 2010-2023, Intel Corporation

  SPDX-License-Identifier: BSD-3-Clause
*/

static int mandel(float c_re, float c_im, int count) {
    float z_re = c_re, z_im = c_im;
    int i;
    for (i = 0; i < count; ++i) {
        if (z_re * z_re + z_im * z_im > 4.f)
            break;

        float new_re = z_re * z_re - z_im * z_im;
        float new_im = 2.f * z_re * z_im;
        z_re = c_re + new_re;
        z_im = c_im + new_im;
    }

    return i;
}

static void mandelbrot_scalar(float x0, float y0, float x1, float y1,
                              int width, int height, int maxIterations,
                              int output[], int threads) {
    float dx = (x1 - x0) / width;
    float dy = (y1 - y0) / height;

    #pragma omp parallel for schedule(dynamic, 1) num_threads(threads)
    for (int j = 0; j < height; ++j) {
        for (int i = 0; i < width; ++i) {
            float x = x0 + i * dx;
            float y = y0 + j * dy;
            output[j * width + i] = mandel(x, y, maxIterations);
        }
    }
}

#if defined(__SSE__)
#include <xmmintrin.h>

static void mandelbrot_simd_sse(float x0, float y0, float x1, float y1,
                                int width, int height, int maxIterations,
                                int output[], int threads) {
    float dx = (x1 - x0) / width;
    float dy = (y1 - y0) / height;
    const __m128 two = _mm_set1_ps(2.f);
    const __m128 four = _mm_set1_ps(4.f);

    #pragma omp parallel for schedule(dynamic, 1) num_threads(threads)
    for (int j = 0; j < height; ++j) {
        float y = y0 + j * dy;
        int i = 0;

        // Interleave two independent four-pixel recurrences. This exposes
        // independent vector work while retaining per-lane escape counts.
        for (; width - i >= 8; i += 8) {
            __m128 c_re0 = _mm_setr_ps(x0 + (i + 0) * dx,
                                       x0 + (i + 1) * dx,
                                       x0 + (i + 2) * dx,
                                       x0 + (i + 3) * dx);
            __m128 c_re1 = _mm_setr_ps(x0 + (i + 4) * dx,
                                       x0 + (i + 5) * dx,
                                       x0 + (i + 6) * dx,
                                       x0 + (i + 7) * dx);
            __m128 c_im = _mm_set1_ps(y);
            __m128 z_re0 = c_re0, z_im0 = c_im;
            __m128 z_re1 = c_re1, z_im1 = c_im;
            int counts0[4] = {0, 0, 0, 0};
            int counts1[4] = {0, 0, 0, 0};
            int active0 = 0;
            int active1 = 0;

            if (maxIterations > 0) {
                counts0[0] = counts0[1] = counts0[2] = counts0[3] = maxIterations;
                counts1[0] = counts1[1] = counts1[2] = counts1[3] = maxIterations;
                active0 = 0x0f;
                active1 = 0x0f;
            }

            for (int iteration = 0;
                 iteration < maxIterations && (active0 | active1) != 0;
                 ++iteration) {
                if (active0 != 0) {
                    __m128 magnitude0 = _mm_add_ps(_mm_mul_ps(z_re0, z_re0),
                                                   _mm_mul_ps(z_im0, z_im0));
                    int escaped0 = _mm_movemask_ps(_mm_cmpgt_ps(magnitude0, four));
                    int newly_escaped0 = active0 & escaped0;
                    for (int lane = 0; lane < 4; ++lane) {
                        if (newly_escaped0 & (1 << lane))
                            counts0[lane] = iteration;
                    }
                    active0 &= ~escaped0;
                    if (active0 != 0) {
                        __m128 new_re0 = _mm_sub_ps(_mm_mul_ps(z_re0, z_re0),
                                                    _mm_mul_ps(z_im0, z_im0));
                        __m128 new_im0 = _mm_mul_ps(_mm_mul_ps(two, z_re0), z_im0);
                        z_re0 = _mm_add_ps(c_re0, new_re0);
                        z_im0 = _mm_add_ps(c_im, new_im0);
                    }
                }

                if (active1 != 0) {
                    __m128 magnitude1 = _mm_add_ps(_mm_mul_ps(z_re1, z_re1),
                                                   _mm_mul_ps(z_im1, z_im1));
                    int escaped1 = _mm_movemask_ps(_mm_cmpgt_ps(magnitude1, four));
                    int newly_escaped1 = active1 & escaped1;
                    for (int lane = 0; lane < 4; ++lane) {
                        if (newly_escaped1 & (1 << lane))
                            counts1[lane] = iteration;
                    }
                    active1 &= ~escaped1;
                    if (active1 != 0) {
                        __m128 new_re1 = _mm_sub_ps(_mm_mul_ps(z_re1, z_re1),
                                                    _mm_mul_ps(z_im1, z_im1));
                        __m128 new_im1 = _mm_mul_ps(_mm_mul_ps(two, z_re1), z_im1);
                        z_re1 = _mm_add_ps(c_re1, new_re1);
                        z_im1 = _mm_add_ps(c_im, new_im1);
                    }
                }
            }

            for (int lane = 0; lane < 4; ++lane) {
                output[j * width + i + lane] = counts0[lane];
                output[j * width + i + 4 + lane] = counts1[lane];
            }
        }

        for (; width - i >= 4; i += 4) {
            __m128 c_re = _mm_setr_ps(x0 + (i + 0) * dx,
                                      x0 + (i + 1) * dx,
                                      x0 + (i + 2) * dx,
                                      x0 + (i + 3) * dx);
            __m128 c_im = _mm_set1_ps(y);
            __m128 z_re = c_re;
            __m128 z_im = c_im;
            int counts[4] = {0, 0, 0, 0};
            int active = 0;

            if (maxIterations > 0) {
                counts[0] = counts[1] = counts[2] = counts[3] = maxIterations;
                active = 0x0f;
            }

            for (int iteration = 0; iteration < maxIterations && active != 0;
                 ++iteration) {
                __m128 magnitude = _mm_add_ps(_mm_mul_ps(z_re, z_re),
                                              _mm_mul_ps(z_im, z_im));
                int escaped = _mm_movemask_ps(_mm_cmpgt_ps(magnitude, four));
                int newly_escaped = active & escaped;

                for (int lane = 0; lane < 4; ++lane) {
                    if (newly_escaped & (1 << lane))
                        counts[lane] = iteration;
                }
                active &= ~escaped;
                if (active == 0)
                    break;

                __m128 new_re = _mm_sub_ps(_mm_mul_ps(z_re, z_re),
                                           _mm_mul_ps(z_im, z_im));
                __m128 new_im = _mm_mul_ps(_mm_mul_ps(two, z_re), z_im);
                z_re = _mm_add_ps(c_re, new_re);
                z_im = _mm_add_ps(c_im, new_im);
            }

            for (int lane = 0; lane < 4; ++lane)
                output[j * width + i + lane] = counts[lane];
        }

        for (; i < width; ++i) {
            float x = x0 + i * dx;
            output[j * width + i] = mandel(x, y, maxIterations);
        }
    }
}
#endif

static void mandelbrot_serial(float x0, float y0, float x1, float y1,
                              int width, int height, int maxIterations,
                              int output[], int threads) {
#if defined(__SSE__)
    mandelbrot_simd_sse(x0, y0, x1, y1, width, height, maxIterations,
                        output, threads);
#else
    mandelbrot_scalar(x0, y0, x1, y1, width, height, maxIterations,
                      output, threads);
#endif
}

extern "C" void run(const void* input1, const void* input2, void* output,
                    int n, int parameter, int threads) {
    (void)input2;
    const float* a = static_cast<const float*>(input1);
    mandelbrot_serial(a[0], a[1], a[2], a[3], n * 3 / 2, n, parameter,
                      static_cast<int*>(output), threads);
}
