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

#ifdef _OPENMP
#include <omp.h>
#endif

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

struct Pcg32 {
    uint64_t state;
    uint64_t increment;
};

static inline uint64_t mix_seed(uint64_t value) {
    value += 0x9e3779b97f4a7c15ULL;
    value = (value ^ (value >> 30)) * 0xbf58476d1ce4e5b9ULL;
    value = (value ^ (value >> 27)) * 0x94d049bb133111ebULL;
    return value ^ (value >> 31);
}

static inline uint32_t pcg32_next(Pcg32 &rng) {
    const uint64_t oldstate = rng.state;
    rng.state = oldstate * 6364136223846793005ULL + rng.increment;
    const uint32_t xorshifted = static_cast<uint32_t>(((oldstate >> 18u) ^ oldstate) >> 27u);
    const uint32_t rotation = static_cast<uint32_t>(oldstate >> 59u);
    return (xorshifted >> rotation) | (xorshifted << ((-rotation) & 31));
}

static inline void seed_rng(Pcg32 &rng, uint32_t worker_id) {
    const uint64_t stream = static_cast<uint64_t>(worker_id);
    rng.state = 0;
    rng.increment = (stream << 1u) | 1u;
    pcg32_next(rng);
    rng.state += mix_seed(0x853c49e6748fea9bULL + stream);
    pcg32_next(rng);
}

static inline float uniform01(Pcg32 &rng) {
    return static_cast<float>(pcg32_next(rng) >> 8) * (1.0f / 16777216.0f);
}

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

static float ambient_occlusion(const Isect &isect, const Plane &plane, const Sphere spheres[3], Pcg32 &rng) {
    const float eps = 0.0001f;
    vec p = isect.p + eps * isect.n;
    vec basis[3];
    float occlusion = 0.0f;

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

            for (int snum = 0; snum < 3; ++snum) {
                ray_sphere_intersect(occIsect, ray, spheres[snum]);
                if (occIsect.hit)
                    break;
            }
            if (!occIsect.hit)
                ray_plane_intersect(occIsect, ray, plane);

            if (occIsect.hit)
                occlusion += 1.f;
        }
    }

    occlusion = (ntheta * nphi - occlusion) / (float)(ntheta * nphi);
    return occlusion;
}

static void ao_render_row(int y, int w, int h, int nsubsamples, float image[], const Plane &plane,
                          const Sphere spheres[3], Pcg32 &rng) {
    for (int x = 0; x < w; ++x) {
        const int offset = 3 * (y * w + x);
        float pixel_sum = 0.f;

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

                pixel_sum += ret;
            }
        }

        const float sample_count = static_cast<float>(nsubsamples) * static_cast<float>(nsubsamples);
        const float pixel = pixel_sum / sample_count;
        image[offset + 0] = pixel;
        image[offset + 1] = pixel;
        image[offset + 2] = pixel;
    }
}

static void ao_render(int w, int h, int nsubsamples, float image[], int threads) {
    static Plane plane = {vec(0.0f, -0.5f, 0.0f), vec(0.f, 1.f, 0.f)};
    static Sphere spheres[3] = {
        {vec(-2.0f, 0.0f, -3.5f), 0.5f}, {vec(-0.5f, 0.0f, -3.0f), 0.5f}, {vec(1.0f, 0.0f, -2.2f), 0.5f}};

    if (threads <= 1) {
        Pcg32 rng;
        seed_rng(rng, 0);
        for (int y = 0; y < h; ++y)
            ao_render_row(y, w, h, nsubsamples, image, plane, spheres, rng);
        return;
    }

#ifdef _OPENMP
#pragma omp parallel num_threads(threads)
    {
        Pcg32 rng;
        seed_rng(rng, static_cast<uint32_t>(omp_get_thread_num()));

#pragma omp for schedule(static, 1)
        for (int y = 0; y < h; ++y)
            ao_render_row(y, w, h, nsubsamples, image, plane, spheres, rng);
    }
#else
    Pcg32 rng;
    seed_rng(rng, 0);
    for (int y = 0; y < h; ++y)
        ao_render_row(y, w, h, nsubsamples, image, plane, spheres, rng);
#endif
}

void ao_serial(int w, int h, int nsubsamples, float image[]) {
    ao_render(w, h, nsubsamples, image, 1);
}

#include "render_context.h"
extern "C" void run(RenderInput *c, float *image, int *ids, int threads) {
    (void)ids;
    ao_render(c->width, c->height, c->nsubsamples, image, threads);
}
