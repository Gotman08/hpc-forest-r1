/*
  Copyright (c) 2011-2023, Intel Corporation

  SPDX-License-Identifier: BSD-3-Clause
*/

#include <algorithm>
#include <cstddef>
#include <assert.h>
#include <math.h>

// Just enough of a float3 class to do what we need in this file.
struct float3 {
    float3() { x = y = z = pad = 0.; }
    float3(float xx, float yy, float zz) {
        x = xx;
        y = yy;
        z = zz;
        pad = 0.;
    }

    float3 operator*(float f) const { return float3(x * f, y * f, z * f); }
    float3 operator-(const float3 &f2) const { return float3(x - f2.x, y - f2.y, z - f2.z); }
    float3 operator*(const float3 &f2) const { return float3(x * f2.x, y * f2.y, z * f2.z); }
    float3 operator+(const float3 &f2) const { return float3(x + f2.x, y + f2.y, z + f2.z); }
    float3 operator/(const float3 &f2) const { return float3(x / f2.x, y / f2.y, z / f2.z); }
    float operator[](int i) const { return (&x)[i]; }
    float &operator[](int i) { return (&x)[i]; }

    float x, y, z;
    float pad; // match padding/alignment of ispc version
}
#ifndef _MSC_VER
__attribute__((aligned(16)))
#endif
;

struct Ray {
    float3 origin, dir;
};

static void generateRay(const float raster2camera[4][4], const float camera2world[4][4], float x, float y, Ray &ray) {
    // transform raster coordinate (x, y, 0) to camera space
    float camx = raster2camera[0][0] * x + raster2camera[0][1] * y + raster2camera[0][3];
    float camy = raster2camera[1][0] * x + raster2camera[1][1] * y + raster2camera[1][3];
    float camz = raster2camera[2][3];
    float camw = raster2camera[3][3];
    camx /= camw;
    camy /= camw;
    camz /= camw;

    ray.dir.x = camera2world[0][0] * camx + camera2world[0][1] * camy + camera2world[0][2] * camz;
    ray.dir.y = camera2world[1][0] * camx + camera2world[1][1] * camy + camera2world[1][2] * camz;
    ray.dir.z = camera2world[2][0] * camx + camera2world[2][1] * camy + camera2world[2][2] * camz;

    ray.origin.x = camera2world[0][3] / camera2world[3][3];
    ray.origin.y = camera2world[1][3] / camera2world[3][3];
    ray.origin.z = camera2world[2][3] / camera2world[3][3];
}

static bool Inside(float3 p, float3 pMin, float3 pMax) {
    return (p.x >= pMin.x && p.x <= pMax.x && p.y >= pMin.y && p.y <= pMax.y && p.z >= pMin.z && p.z <= pMax.z);
}

static bool IntersectP(const Ray &ray, float3 pMin, float3 pMax, float *hit0, float *hit1) {
    float t0 = -1e30f, t1 = 1e30f;

    float3 tNear = (pMin - ray.origin) / ray.dir;
    float3 tFar = (pMax - ray.origin) / ray.dir;
    if (tNear.x > tFar.x) {
        float tmp = tNear.x;
        tNear.x = tFar.x;
        tFar.x = tmp;
    }
    t0 = std::max(tNear.x, t0);
    t1 = std::min(tFar.x, t1);

    if (tNear.y > tFar.y) {
        float tmp = tNear.y;
        tNear.y = tFar.y;
        tFar.y = tmp;
    }
    t0 = std::max(tNear.y, t0);
    t1 = std::min(tFar.y, t1);

    if (tNear.z > tFar.z) {
        float tmp = tNear.z;
        tNear.z = tFar.z;
        tFar.z = tmp;
    }
    t0 = std::max(tNear.z, t0);
    t1 = std::min(tFar.z, t1);

    if (t0 <= t1) {
        *hit0 = t0;
        *hit1 = t1;
        return true;
    } else
        return false;
}

static inline float Lerp(float t, float a, float b) { return (1.f - t) * a + t * b; }

static inline int Clamp(int v, int low, int high) { return std::min(std::max(v, low), high); }

static inline float D(int x, int y, int z, int nVoxels[3], float density[]) {
    x = Clamp(x, 0, nVoxels[0] - 1);
    y = Clamp(y, 0, nVoxels[1] - 1);
    z = Clamp(z, 0, nVoxels[2] - 1);
    return density[z * nVoxels[0] * nVoxels[1] + y * nVoxels[0] + x];
}

static inline float3 MakeDensityScale(float3 pMin, float3 pMax, int nVoxels[3]) {
    return float3(static_cast<float>(nVoxels[0]) / (pMax.x - pMin.x),
                  static_cast<float>(nVoxels[1]) / (pMax.y - pMin.y),
                  static_cast<float>(nVoxels[2]) / (pMax.z - pMin.z));
}

static inline float Density(float3 Pobj, float3 pMin, float3 pMax, float density[], int nVoxels[3],
                            const float3 &densityScale) {
    if (!Inside(Pobj, pMin, pMax))
        return 0;
    // Compute voxel coordinates and offsets for _Pobj_
    float3 vox((Pobj.x - pMin.x) * densityScale.x - .5f, (Pobj.y - pMin.y) * densityScale.y - .5f,
               (Pobj.z - pMin.z) * densityScale.z - .5f);
    int vx = (int)(vox.x), vy = (int)(vox.y), vz = (int)(vox.z);
    float dx = vox.x - vx, dy = vox.y - vy, dz = vox.z - vz;

    // Trilinearly interpolate density values to compute local density
    float d00 = Lerp(dx, D(vx, vy, vz, nVoxels, density), D(vx + 1, vy, vz, nVoxels, density));
    float d10 = Lerp(dx, D(vx, vy + 1, vz, nVoxels, density), D(vx + 1, vy + 1, vz, nVoxels, density));
    float d01 = Lerp(dx, D(vx, vy, vz + 1, nVoxels, density), D(vx + 1, vy, vz + 1, nVoxels, density));
    float d11 = Lerp(dx, D(vx, vy + 1, vz + 1, nVoxels, density), D(vx + 1, vy + 1, vz + 1, nVoxels, density));
    float d0 = Lerp(dy, d00, d10);
    float d1 = Lerp(dy, d01, d11);
    return Lerp(dz, d0, d1);
}

static float transmittance(float3 p0, float3 p1, float3 pMin, float3 pMax, float sigma_t, float density[],
                           int nVoxels[3], const float3 &densityScale) {
    float rayT0, rayT1;
    Ray ray;
    ray.origin = p1;
    ray.dir = p0 - p1;

    // Find the parametric t range along the ray that is inside the volume.
    if (!IntersectP(ray, pMin, pMax, &rayT0, &rayT1))
        return 1.;

    rayT0 = std::max(rayT0, 0.f);

    // Accumulate beam transmittance in tau
    float tau = 0;
    float rayLength = sqrtf(ray.dir.x * ray.dir.x + ray.dir.y * ray.dir.y + ray.dir.z * ray.dir.z);
    float stepDist = 0.2f;
    float stepT = stepDist / rayLength;

    float t = rayT0;
    float3 pos = ray.origin + ray.dir * rayT0;
    float3 dirStep = ray.dir * stepT;
    while (t < rayT1) {
        tau += stepDist * sigma_t * Density(pos, pMin, pMax, density, nVoxels, densityScale);
        pos = pos + dirStep;
        t += stepT;
    }

    return expf(-tau);
}

static float distanceSquared(float3 a, float3 b) {
    float3 d = a - b;
    return d.x * d.x + d.y * d.y + d.z * d.z;
}

static float raymarch(float density[], int nVoxels[3], const Ray &ray, float3 pMin, float3 pMax,
                      const float3 &densityScale) {
    float3 lightPos(-1.f, 4.f, 1.5f);

    if (!IntersectP(ray, pMin, pMax, &rayT0, &rayT1))
        return 0.;

    rayT0 = std::max(rayT0, 0.f);

    // Parameters that define the volume scattering characteristics and
    // sampling rate for raymarching
    float Le = .25f;           // Emission coefficient
    float sigma_a = 10;        // Absorption coefficient
    float sigma_s = 10;        // Scattering coefficient
    float stepDist = 0.025f;   // Ray step amount
    float lightIntensity = 40; // Light source intensity

    float tau = 0.f; // accumulated beam transmittance
    float L = 0;     // radiance along the ray
    float rayLength = sqrtf(ray.dir.x * ray.dir.x + ray.dir.y * ray.dir.y + ray.dir.z * ray.dir.z);
    float stepT = stepDist / rayLength;

    float t = rayT0;
    float3 pos = ray.origin + ray.dir * rayT0;
    float3 dirStep = ray.dir * stepT;
    while (t < rayT1) {
        float d = Density(pos, pMin, pMax, density, nVoxels, densityScale);

        // terminate once attenuation is high
        float atten = expf(-tau);
        if (atten < .005f)
            break;

        // direct lighting
        float Li = 0.f;
        if (d != 0.f) {
            Li = lightIntensity / distanceSquared(lightPos, pos) *
                 transmittance(lightPos, pos, pMin, pMax, sigma_a + sigma_s, density, nVoxels, densityScale);
        }
        L += stepDist * atten * d * sigma_s * (Li + Le);

        // update beam transmittance
        tau += stepDist * (sigma_a + sigma_s) * d;

        pos = pos + dirStep;
        t += stepT;
    }

    // Gamma correction
    return powf(L, 1.f / 2.2f);
}

static inline void renderPixel(float density[], int nVoxels[3], const float raster2camera[4][4],
                               const float camera2world[4][4], int width, int x, int y, float image[],
                               float3 pMin, float3 pMax, const float3 &densityScale) {
    std::size_t offset = static_cast<std::size_t>(y) * static_cast<std::size_t>(width) + static_cast<std::size_t>(x);
    Ray ray;
    generateRay(raster2camera, camera2world, static_cast<float>(x), static_cast<float>(y), ray);
    image[offset] = raymarch(density, nVoxels, ray, pMin, pMax, densityScale);
}

void volume_serial(float density[], int nVoxels[3], const float raster2camera[4][4], const float camera2world[4][4],
                   int width, int height, float image[], int threads) {
    if (width <= 0 || height <= 0)
        return;

    const std::size_t pixel_count = static_cast<std::size_t>(width) * static_cast<std::size_t>(height);
    const float3 pMin(.3f, -.2f, .3f), pMax(1.8f, 2.3f, 1.8f);
    const float3 densityScale = MakeDensityScale(pMin, pMax, nVoxels);
    if (threads <= 1 || pixel_count == 1) {
        for (int y = 0; y < height; ++y)
            for (int x = 0; x < width; ++x)
                renderPixel(density, nVoxels, raster2camera, camera2world, width, x, y, image, pMin, pMax,
                            densityScale);
        return;
    }

    const int team_size = pixel_count < static_cast<std::size_t>(threads) ? static_cast<int>(pixel_count) : threads;
#pragma omp parallel for collapse(2) schedule(dynamic, 256) num_threads(team_size)
    for (int y = 0; y < height; ++y) {
        for (int x = 0; x < width; ++x)
            renderPixel(density, nVoxels, raster2camera, camera2world, width, x, y, image, pMin, pMax, densityScale);
    }
}

#include <cstring>
#include "render_context.h"
extern "C" void run(RenderInput*c,float*image,int*ids,int threads){volume_serial(c->density,c->nvox,c->raster2camera,c->camera2world,c->width,c->height,image,threads);}
