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
#include <stdlib.h>
#include <stddef.h>
#include <stdint.h>

#ifdef _MSC_VER
static long long drand48_x = 0x1234ABCD330E;

static inline void srand48(int x) { drand48_x = x ^ (x << 16); }

static inline double drand48() {
    drand48_x = drand48_x * 0x5DEECE66D + 0xB;
    return (drand48_x & 0xFFFFFFFFFFFF) * (1.0 / 281474976710656.0);
}
#endif // _MSC_VER

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

static inline void ray_plane_intersect(Isect &isect, Ray &ray, Plane &plane) {
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

static inline void ray_sphere_intersect(Isect &isect, Ray &ray, Sphere &sphere) {
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

static inline uint64_t splitmix64_mix(uint64_t value) {
    value = (value ^ (value >> 30)) * 0xBF58476D1CE4E5B9ULL;
    value = (value ^ (value >> 27)) * 0x94D049BB133111EBULL;
    return value ^ (value >> 31);
}

static inline uint64_t splitmix64_next(uint64_t &state) {
    state += 0x9E3779B97F4A7C15ULL;
    return splitmix64_mix(state);
}

static inline double uniform01(uint64_t &state) {
    return (double)(splitmix64_next(state) >> 11) * (1.0 / 9007199254740992.0);
}

static float ambient_occlusion(Isect &isect, Plane &plane, Sphere spheres[3], uint64_t &rng) {
    float eps = 0.0001f;
    vec p, n;
    vec basis[3];
    float occlusion = 0.0;

    p = isect.p + eps * isect.n;

    orthoBasis(basis, isect.n);

    static const int ntheta = NAO_SAMPLES;
    static const int nphi = NAO_SAMPLES;
    for (int j = 0; j < ntheta; j++) {
        for (int i = 0; i < nphi; i++) {
            Ray ray;
            Isect occIsect;

            float theta = sqrtf(uniform01(rng));
            float phi = 2.0f * M_PI * uniform01(rng);
            float x = cosf(phi) * theta;
            float y = sinf(phi) * theta;
            float z = sqrtf(1.0f - theta * theta);

            // local . global
            float rx = x * basis[0].x + y * basis[1].x + z * basis[2].x;
            float ry = x * basis[0].y + y * basis[1].y + z * basis[2].y;
            float rz = x * basis[0].z + y * basis[1].z + z * basis[2].z;

            ray.org = p;
            ray.dir.x = rx;
            ray.dir.y = ry;
            ray.dir.z = rz;

            occIsect.t = 1.0e+17f;
            occIsect.hit = 0;

            for (int snum = 0; snum < 3; ++snum)
                ray_sphere_intersect(occIsect, ray, spheres[snum]);
            ray_plane_intersect(occIsect, ray, plane);

            if (occIsect.hit)
                occlusion += 1.f;
        }
    }

    occlusion = (ntheta * nphi - occlusion) / (float)(ntheta * nphi);
    return occlusion;
}

static void ao_pixel(size_t pixel_index, int w, int h, int nsubsamples,
                     uint64_t render_seed, Plane &plane, Sphere spheres[3], float image[]) {
    const int x = (int)(pixel_index % (size_t)w);
    const int y = (int)(pixel_index / (size_t)w);
    const size_t offset = 3 * pixel_index;
    uint64_t rng = splitmix64_mix(render_seed +
                                  0x9E3779B97F4A7C15ULL * ((uint64_t)pixel_index + 1ULL));

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
                ray_sphere_intersect(isect, ray, spheres[snum]);
            ray_plane_intersect(isect, ray, plane);

            if (isect.hit)
                ret = ambient_occlusion(isect, plane, spheres, rng);

            // Update image for AO for this ray
            image[offset + 0] += ret;
            image[offset + 1] += ret;
            image[offset + 2] += ret;
        }
    }

    // Normalize image pixels by number of samples taken per pixel
    image[offset + 0] /= nsubsamples * nsubsamples;
    image[offset + 1] /= nsubsamples * nsubsamples;
    image[offset + 2] /= nsubsamples * nsubsamples;
}

/* Compute the image for the scanlines from [y0,y1), for an overall image
   of width w and height h.
 */
static void ao_scanlines(int y0, int y1, int w, int h, int nsubsamples, int threads, float image[]) {
    static Plane plane = {vec(0.0f, -0.5f, 0.0f), vec(0.f, 1.f, 0.f)};
    static Sphere spheres[3] = {
        {vec(-2.0f, 0.0f, -3.5f), 0.5f}, {vec(-0.5f, 0.0f, -3.0f), 0.5f}, {vec(1.0f, 0.0f, -2.2f), 0.5f}};

    // Preserve the existing per-render seed initialization, then use only
    // independent pixel-local streams inside the worker loop.
    srand48(y0);
    const uint64_t render_seed = (uint64_t)(drand48() * 281474976710656.0);
    const size_t first_pixel = (size_t)y0 * (size_t)w;
    const size_t end_pixel = (size_t)y1 * (size_t)w;
    const int worker_count = threads > 1 ? threads : 1;

    if (worker_count == 1 || first_pixel >= end_pixel) {
        for (size_t pixel = first_pixel; pixel < end_pixel; ++pixel)
            ao_pixel(pixel, w, h, nsubsamples, render_seed, plane, spheres, image);
    } else {
        const long long first = (long long)first_pixel;
        const long long end = (long long)end_pixel;
#pragma omp parallel for schedule(dynamic, 16) num_threads(worker_count)
        for (long long pixel = first; pixel < end; ++pixel)
            ao_pixel((size_t)pixel, w, h, nsubsamples, render_seed, plane, spheres, image);
    }
}

void ao_serial(int w, int h, int nsubsamples, float image[]) {
    ao_scanlines(0, h, w, h, nsubsamples, 1, image);
}

#include <cstring>
#include "render_context.h"
extern "C" void run(RenderInput *c, float *image, int *ids, int threads) {
    memset(image, 0, size_t(c->width) * c->height * 3 * 4);
    ao_scanlines(0, c->height, c->width, c->height, c->nsubsamples, threads, image);
}
