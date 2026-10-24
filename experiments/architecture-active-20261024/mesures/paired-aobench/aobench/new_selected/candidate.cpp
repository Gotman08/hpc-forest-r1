// -*- mode: c++ -*-
/*
  Copyright (c) 2010-2023, Intel Corporation

  SPDX-License-Identifier: BSD-3-Clause
*/
/*
  Based on Syoyo Fujita's aobench: http://code.google.com/p/aobench
*/

#ifdef _MSC_VER
#define _CRT_SECURE_NO_WARNINGS
#define NOMINMAX
#pragma warning(disable : 4244)
#pragma warning(disable : 4305)
#endif

#include <math.h>
#include <stdint.h>
#include <stdlib.h>
#include <cstring>

#ifdef _MSC_VER
__declspec(align(16))
#endif
struct vec {
    vec() { x = y = z = pad = 0.; }
    vec(float xx, float yy, float zz) {
        x = xx;
        y = yy;
        z = zz;
        pad = 0.;
    }

    vec operator*(float f) const { return vec(x * f, y * f, z * f); }
    vec operator+(const vec &f2) const { return vec(x + f2.x, y + f2.y, z + f2.z); }
    vec operator-(const vec &f2) const { return vec(x - f2.x, y - f2.y, z - f2.z); }
    vec operator*(const vec &f2) const { return vec(x * f2.x, y * f2.y, z * f2.z); }
    float x, y, z;
    float pad;
}
#ifndef _MSC_VER
__attribute__((aligned(16)))
#endif
;
inline vec operator*(float f, const vec &v) { return vec(f * v.x, f * v.y, f * v.z); }

#define NAO_SAMPLES 8

#ifdef M_PI
#undef M_PI
#endif
#define M_PI 3.1415926535f

struct Isect {
    float t;
    vec p;
    vec n;
    int hit;
};

struct Sphere {
    vec center;
    float radius;
};

struct Plane {
    vec p;
    vec n;
};

struct Ray {
    vec org;
    vec dir;
};

static const Plane kPlane = {vec(0.0f, -0.5f, 0.0f), vec(0.f, 1.f, 0.f)};
static const Sphere kSpheres[3] = {
    {vec(-2.0f, 0.0f, -3.5f), 0.5f},
    {vec(-0.5f, 0.0f, -3.0f), 0.5f},
    {vec(1.0f, 0.0f, -2.2f), 0.5f}};

static inline float dot(const vec &a, const vec &b) { return a.x * b.x + a.y * b.y + a.z * b.z; }

static inline vec vcross(const vec &v0, const vec &v1) {
    vec ret;
    ret.x = v0.y * v1.z - v0.z * v1.y;
    ret.y = v0.z * v1.x - v0.x * v1.z;
    ret.z = v0.x * v1.y - v0.y * v1.x;
    return ret;
}

static inline void vnormalize(vec &v) {
    float len2 = dot(v, v);
    float invlen = 1.f / sqrtf(len2);
    v = v * invlen;
}

static inline void ray_plane_intersect(Isect &isect, const Ray &ray, const Plane &plane) {
    float d = -dot(plane.p, plane.n);
    float v = dot(ray.dir, plane.n);

    if (fabsf(v) < 1.0e-17f)
        return;
    else {
        float t = -(dot(ray.org, plane.n) + d) / v;

        if ((t > 0.0) && (t < isect.t)) {
            isect.t = t;
            isect.hit = 1;
            isect.p = ray.org + ray.dir * t;
            isect.n = plane.n;
        }
    }
}

static inline void ray_sphere_intersect(Isect &isect, const Ray &ray, const Sphere &sphere) {
    vec rs = ray.org - sphere.center;

    float B = dot(rs, ray.dir);
    float C = dot(rs, rs) - sphere.radius * sphere.radius;
    float D = B * B - C;

    if (D > 0.) {
        float t = -B - sqrtf(D);

        if ((t > 0.0) && (t < isect.t)) {
            isect.t = t;
            isect.hit = 1;
            isect.p = ray.org + t * ray.dir;
            isect.n = isect.p - sphere.center;
            vnormalize(isect.n);
        }
    }
}

static inline void orthoBasis(vec basis[3], const vec &n) {
    basis[2] = n;
    basis[1].x = 0.0;
    basis[1].y = 0.0;
    basis[1].z = 0.0;

    if ((n.x < 0.6f) && (n.x > -0.6f)) {
        basis[1].x = 1.0;
    } else if ((n.y < 0.6f) && (n.y > -0.6f)) {
        basis[1].y = 1.0;
    } else if ((n.z < 0.6f) && (n.z > -0.6f)) {
        basis[1].z = 1.0;
    } else {
        basis[1].x = 1.0;
    }

    basis[0] = vcross(basis[1], basis[2]);
    vnormalize(basis[0]);

    basis[1] = vcross(basis[2], basis[0]);
    vnormalize(basis[1]);
}

static inline uint64_t mix64(uint64_t value) {
    value = (value ^ (value >> 30)) * UINT64_C(0xbf58476d1ce4e5b9);
    value = (value ^ (value >> 27)) * UINT64_C(0x94d049bb133111eb);
    return value ^ (value >> 31);
}

static inline uint64_t pixel_rng_state(uint64_t seed, uint64_t pixel) {
    return mix64(seed + (pixel + 1U) * UINT64_C(0x9e3779b97f4a7c15));
}

static inline double uniform01(uint64_t &state) {
    state += UINT64_C(0x9e3779b97f4a7c15);
    return static_cast<double>(mix64(state) >> 11) * (1.0 / 9007199254740992.0);
}

static inline uint64_t next_render_seed() {
    return static_cast<uint64_t>(drand48() * 9007199254740992.0);
}

static float ambient_occlusion(const Isect &isect, const Plane &plane, const Sphere spheres[3], uint64_t &rng_state) {
    float eps = 0.0001f;
    vec p, n;
    vec basis[3];
    float occlusion = 0.0;

    p = isect.p + eps * isect.n;

    orthoBasis(basis, isect.n);

    static const int ntheta = NAO_SAMPLES;
    static const int nphi = NAO_SAMPLES;
    enum { ray_count = NAO_SAMPLES * NAO_SAMPLES };
    float direction_x[ray_count];
    float direction_y[ray_count];
    float direction_z[ray_count];
    float nearest_t[ray_count];
    int ray_hit[ray_count];

    int ray_index = 0;
    for (int j = 0; j < ntheta; j++) {
        for (int i = 0; i < nphi; i++) {
            float theta = sqrtf(uniform01(rng_state));
            float phi = 2.0f * M_PI * uniform01(rng_state);
            float x = cosf(phi) * theta;
            float y = sinf(phi) * theta;
            float z = sqrtf(1.0f - theta * theta);

            // local . global
            float rx = x * basis[0].x + y * basis[1].x + z * basis[2].x;
            float ry = x * basis[0].y + y * basis[1].y + z * basis[2].y;
            float rz = x * basis[0].z + y * basis[1].z + z * basis[2].z;

            direction_x[ray_index] = rx;
            direction_y[ray_index] = ry;
            direction_z[ray_index] = rz;
            nearest_t[ray_index] = 1.0e+17f;
            ray_hit[ray_index] = 0;
            ++ray_index;
        }
    }

    for (int snum = 0; snum < 3; ++snum) {
        const Sphere &sphere = spheres[snum];
        const vec rs = p - sphere.center;
        const float C = dot(rs, rs) - sphere.radius * sphere.radius;

        for (int lane = 0; lane < ray_count; ++lane) {
            const float B = rs.x * direction_x[lane] + rs.y * direction_y[lane] + rs.z * direction_z[lane];
            const float D = B * B - C;

            if (D > 0.) {
                const float t = -B - sqrtf(D);

                if ((t > 0.0f) && (t < nearest_t[lane])) {
                    nearest_t[lane] = t;
                    ray_hit[lane] = 1;
                }
            }
        }
    }

    const float plane_d = -dot(plane.p, plane.n);
    for (int lane = 0; lane < ray_count; ++lane) {
        const float v = direction_x[lane] * plane.n.x + direction_y[lane] * plane.n.y + direction_z[lane] * plane.n.z;

        if (fabsf(v) < 1.0e-17f)
            continue;

        const float t = -(dot(p, plane.n) + plane_d) / v;
        if ((t > 0.0f) && (t < nearest_t[lane])) {
            nearest_t[lane] = t;
            ray_hit[lane] = 1;
        }
    }

    for (int lane = 0; lane < ray_count; ++lane) {
        if (ray_hit[lane])
            occlusion += 1.f;
    }

    occlusion = (ntheta * nphi - occlusion) / (float)(ntheta * nphi);
    return occlusion;
}

static inline void ao_pixel(long long pixel_index, int w, int h, int nsubsamples, uint64_t seed, float image[]) {
    int y = static_cast<int>(pixel_index / w);
    int x = static_cast<int>(pixel_index - static_cast<long long>(y) * w);
    size_t offset = static_cast<size_t>(pixel_index) * 3U;
    uint64_t rng_state = pixel_rng_state(seed, static_cast<uint64_t>(pixel_index));
    float sample_sum = 0.f;

    for (int u = 0; u < nsubsamples; ++u) {
        for (int v = 0; v < nsubsamples; ++v) {
            float px = (x + (u / (float)nsubsamples) - (w / 2.0f)) / (w / 2.0f);
            float py = -(y + (v / (float)nsubsamples) - (h / 2.0f)) / (h / 2.0f);

            // Scale NDC based on width/height ratio, supporting non-square image output
            px *= (float)w / (float)h;

            float ret = 0.f;
            Ray ray;
            Isect isect;

            ray.org = vec(0.f, 0.f, 0.f);

            ray.dir.x = px;
            ray.dir.y = py;
            ray.dir.z = -1.0f;
            vnormalize(ray.dir);

            isect.t = 1.0e+17f;
            isect.hit = 0;

            for (int snum = 0; snum < 3; ++snum)
                ray_sphere_intersect(isect, ray, kSpheres[snum]);
            ray_plane_intersect(isect, ray, kPlane);

            if (isect.hit)
                ret = ambient_occlusion(isect, kPlane, kSpheres, rng_state);

            sample_sum += ret;
        }
    }

    const long long sample_count = static_cast<long long>(nsubsamples) * nsubsamples;
    const float pixel_value = sample_sum / static_cast<float>(sample_count);
    image[offset + 0] = pixel_value;
    image[offset + 1] = pixel_value;
    image[offset + 2] = pixel_value;
}

static void ao_render(int w, int h, int nsubsamples, uint64_t seed, int threads, float image[]) {
    const long long total_pixels = static_cast<long long>(w) * h;
    const int worker_count = threads > 0 ? threads : 1;

    if (worker_count == 1) {
        for (long long pixel = 0; pixel < total_pixels; ++pixel)
            ao_pixel(pixel, w, h, nsubsamples, seed, image);
    } else {
#pragma omp parallel for schedule(dynamic, 64) num_threads(worker_count) default(none) shared(image, total_pixels, w, h, nsubsamples, seed, worker_count, kPlane, kSpheres)
        for (long long pixel = 0; pixel < total_pixels; ++pixel)
            ao_pixel(pixel, w, h, nsubsamples, seed, image);
    }
}

void ao_serial(int w, int h, int nsubsamples, float image[]) {
    ao_render(w, h, nsubsamples, next_render_seed(), 1, image);
}

#include "render_context.h"
extern "C" void run(RenderInput *c, float *image, int *ids, int threads) {
    const int width = c->width;
    const int height = c->height;
    const int nsubsamples = c->nsubsamples;
    memset(image, 0, size_t(width) * height * 3 * sizeof(float));
    ao_render(width, height, nsubsamples, next_render_seed(), threads, image);
}
