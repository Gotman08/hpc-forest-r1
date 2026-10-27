/*
  Copyright (c) 2010-2023, Intel Corporation

  SPDX-License-Identifier: BSD-3-Clause
*/

#include <emmintrin.h>
#include <limits>

static int mandel(float c_re, float c_im, int count) {
    const bool binary32 = std::numeric_limits<float>::is_iec559 &&
                          std::numeric_limits<float>::radix == 2 &&
                          std::numeric_limits<float>::digits == 24 &&
                          std::numeric_limits<float>::max_exponent == 128;
    if (count > 0 && binary32) {
        if (c_re >= -0.25f && c_re <= 0.25f &&
            c_im >= -0.25f && c_im <= 0.25f) {
            const float norm2 = c_re * c_re + c_im * c_im;
            if (norm2 <= 0.0624694869f)
                return count;
        }

        const float offset_re = c_re + 0.25f;
        if (offset_re >= -0.125f && offset_re <= 0.125f &&
            c_im >= -0.125f && c_im <= 0.125f) {
            const float offset_norm2 = offset_re * offset_re + c_im * c_im;
            if (offset_norm2 <= 441.0f / 65536.0f)
                return count;
        }
    }

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

static inline void mandel_row(float x0, float y, float dx, int j,
                              int width, int maxIterations, int output[]) {
    int i = 0;
    const __m128 x0v = _mm_set1_ps(x0);
    const __m128 dxv = _mm_set1_ps(dx);
    const __m128 four = _mm_set1_ps(4.f);
    const __m128 two = _mm_set1_ps(2.f);
    const __m128 yv = _mm_set1_ps(y);

    for (; i + 4 <= width; i += 4) {
        const __m128i indices = _mm_set_epi32(i + 3, i + 2, i + 1, i);
        const __m128 lane_indices = _mm_cvtepi32_ps(indices);
        const __m128 c_re = _mm_add_ps(x0v, _mm_mul_ps(lane_indices, dxv));
        __m128 z_re = c_re;
        __m128 z_im = yv;
        __m128i active = _mm_set1_epi32(-1);
        __m128i pixel_counts = _mm_setzero_si128();

        const bool binary32 = std::numeric_limits<float>::is_iec559 &&
                              std::numeric_limits<float>::radix == 2 &&
                              std::numeric_limits<float>::digits == 24 &&
                              std::numeric_limits<float>::max_exponent == 128;
        if (maxIterations > 0 && binary32) {
            const __m128 central_box = _mm_and_ps(
                _mm_and_ps(_mm_cmpge_ps(c_re, _mm_set1_ps(-0.25f)),
                           _mm_cmple_ps(c_re, _mm_set1_ps(0.25f))),
                _mm_and_ps(_mm_cmpge_ps(yv, _mm_set1_ps(-0.25f)),
                           _mm_cmple_ps(yv, _mm_set1_ps(0.25f))));
            __m128i central = _mm_setzero_si128();
            if (_mm_movemask_epi8(_mm_castps_si128(central_box)) != 0) {
                const __m128 re_squared = _mm_mul_ps(c_re, c_re);
                const __m128 im_squared = _mm_mul_ps(yv, yv);
                const __m128 norm2 = _mm_add_ps(re_squared, im_squared);
                const __m128 in_disk = _mm_and_ps(
                    central_box,
                    _mm_cmple_ps(norm2, _mm_set1_ps(0.0624694869f)));
                central = _mm_castps_si128(in_disk);
            }

            const __m128 offset_re = _mm_add_ps(c_re, _mm_set1_ps(0.25f));
            const __m128 offset_box = _mm_and_ps(
                _mm_and_ps(_mm_cmpge_ps(offset_re, _mm_set1_ps(-0.125f)),
                           _mm_cmple_ps(offset_re, _mm_set1_ps(0.125f))),
                _mm_and_ps(_mm_cmpge_ps(yv, _mm_set1_ps(-0.125f)),
                           _mm_cmple_ps(yv, _mm_set1_ps(0.125f))));
            __m128i period2 = _mm_setzero_si128();
            if (_mm_movemask_epi8(_mm_castps_si128(offset_box)) != 0) {
                const __m128 re_squared = _mm_mul_ps(offset_re, offset_re);
                const __m128 im_squared = _mm_mul_ps(yv, yv);
                const __m128 norm2 = _mm_add_ps(re_squared, im_squared);
                const __m128 in_disk = _mm_and_ps(
                    offset_box,
                    _mm_cmple_ps(norm2, _mm_set1_ps(441.0f / 65536.0f)));
                period2 = _mm_castps_si128(in_disk);
            }

            const __m128i interior = _mm_or_si128(central, period2);
            pixel_counts = _mm_and_si128(
                interior, _mm_set1_epi32(maxIterations));
            active = _mm_andnot_si128(interior, active);
        }

        for (int iter = 0; iter < maxIterations; ++iter) {
            if (_mm_movemask_epi8(active) == 0)
                break;

            const __m128 re_squared = _mm_mul_ps(z_re, z_re);
            const __m128 im_squared = _mm_mul_ps(z_im, z_im);
            const __m128 magnitude_squared = _mm_add_ps(re_squared, im_squared);
            const __m128 escaped = _mm_cmpgt_ps(magnitude_squared, four);

            active = _mm_andnot_si128(_mm_castps_si128(escaped), active);
            if (_mm_movemask_epi8(active) == 0)
                break;

            pixel_counts = _mm_sub_epi32(pixel_counts, active);

            const __m128 new_re = _mm_sub_ps(re_squared, im_squared);
            const __m128 new_im = _mm_mul_ps(_mm_mul_ps(two, z_re), z_im);
            z_re = _mm_add_ps(c_re, new_re);
            z_im = _mm_add_ps(yv, new_im);
        }

        int lane_counts[4];
        _mm_storeu_si128(reinterpret_cast<__m128i *>(lane_counts), pixel_counts);
        for (int lane = 0; lane < 4; ++lane)
            output[j * width + i + lane] = lane_counts[lane];
    }

    for (; i < width; ++i) {
        float x = x0 + i * dx;
        output[j * width + i] = mandel(x, y, maxIterations);
    }
}

static void mandelbrot_simd(float x0, float y0, float x1, float y1,
                            int width, int height, int maxIterations, int output[],
                            int threads) {
    float dx = (x1 - x0) / width;
    float dy = (y1 - y0) / height;

    if (threads <= 1) {
        for (int j = 0; j < height; ++j) {
            float y = y0 + j * dy;
            mandel_row(x0, y, dx, j, width, maxIterations, output);
        }
    } else {
        #pragma omp parallel for schedule(dynamic, 2) num_threads(threads)
        for (int j = 0; j < height; ++j) {
            float y = y0 + j * dy;
            mandel_row(x0, y, dx, j, width, maxIterations, output);
        }
    }
}

#include <cstdint>
#include <cstring>
#include <cmath>
#include <algorithm>
#include <omp.h>

extern "C" void run(const void* input1, const void* input2, void* output,
                    int n, int parameter, int threads) {
    const float* a = (const float*)input1;
    mandelbrot_simd(a[0], a[1], a[2], a[3], n * 3 / 2, n, parameter,
                    (int*)output, threads);
}
