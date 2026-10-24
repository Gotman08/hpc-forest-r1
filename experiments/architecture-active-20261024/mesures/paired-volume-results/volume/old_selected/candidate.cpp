/*
  Copyright (c) 2011-2023, Intel Corporation

  SPDX-License-Identifier: BSD-3-Clause
*/

#include <algorithm>
#include <assert.h>
#include <math.h>
#include <cstddef>

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

static inline float D(int x, int y, int z, const int nVoxels[3], const float density[]) {
    x = Clamp(x, 0, nVoxels[0] - 1);
    y = Clamp(y, 0, nVoxels[1] - 1);
    z = Clamp(z, 0, nVoxels[2] - 1);
    return density[z * nVoxels[0] * nVoxels[1] + y * nVoxels[0] + x];
}

struct DensityGrid {
    float3 pMin, pMax;
    float scaleX, scaleY, scaleZ;
    int nVoxels[3];
    std::size_t rowStride, sliceStride;
};

static inline DensityGrid MakeDensityGrid(int nVoxels[3]) {
    DensityGrid grid;
    grid.pMin = float3(.3f, -.2f, .3f);
    grid.pMax = float3(1.8f, 2.3f, 1.8f);
    grid.nVoxels[0] = nVoxels[0];
    grid.nVoxels[1] = nVoxels[1];
    grid.nVoxels[2] = nVoxels[2];
    grid.scaleX = static_cast<float>(nVoxels[0]) / (grid.pMax.x - grid.pMin.x);
    grid.scaleY = static_cast<float>(nVoxels[1]) / (grid.pMax.y - grid.pMin.y);
    grid.scaleZ = static_cast<float>(nVoxels[2]) / (grid.pMax.z - grid.pMin.z);
    grid.rowStride = static_cast<std::size_t>(nVoxels[0]);
    grid.sliceStride = grid.rowStride * static_cast<std::size_t>(nVoxels[1]);
    return grid;
}

static inline float Density(float3 Pobj, const DensityGrid &grid, const float density[]) {
    if (!Inside(Pobj, grid.pMin, grid.pMax))
        return 0;

    // Scale coordinates and compute the voxel offsets for this sample.
    float voxX = (Pobj.x - grid.pMin.x) * grid.scaleX - .5f;
    float voxY = (Pobj.y - grid.pMin.y) * grid.scaleY - .5f;
    float voxZ = (Pobj.z - grid.pMin.z) * grid.scaleZ - .5f;
    int vx = static_cast<int>(voxX), vy = static_cast<int>(voxY), vz = static_cast<int>(voxZ);
    float dx = voxX - vx, dy = voxY - vy, dz = voxZ - vz;

    // Interior samples can read the eight neighbors directly; edge samples
    // retain the original independently clamped access path.
    if (vx >= 0 && vx < grid.nVoxels[0] - 1 && vy >= 0 && vy < grid.nVoxels[1] - 1 &&
        vz >= 0 && vz < grid.nVoxels[2] - 1) {
        const std::size_t base = static_cast<std::size_t>(vz) * grid.sliceStride +
                                 static_cast<std::size_t>(vy) * grid.rowStride + static_cast<std::size_t>(vx);
        const float *v = density + base;
        float d00 = Lerp(dx, v[0], v[1]);
        float d10 = Lerp(dx, v[grid.rowStride], v[grid.rowStride + 1]);
        float d01 = Lerp(dx, v[grid.sliceStride], v[grid.sliceStride + 1]);
        float d11 = Lerp(dx, v[grid.sliceStride + grid.rowStride], v[grid.sliceStride + grid.rowStride + 1]);
        float d0 = Lerp(dy, d00, d10);
        float d1 = Lerp(dy, d01, d11);
        return Lerp(dz, d0, d1);
    }

    // Clamp each axis once, then reuse the resulting row and slice addresses
    // for all eight contributors at the volume boundary.
    const int x0 = Clamp(vx, 0, grid.nVoxels[0] - 1);
    const int x1 = Clamp(vx + 1, 0, grid.nVoxels[0] - 1);
    const int y0 = Clamp(vy, 0, grid.nVoxels[1] - 1);
    const int y1 = Clamp(vy + 1, 0, grid.nVoxels[1] - 1);
    const int z0 = Clamp(vz, 0, grid.nVoxels[2] - 1);
    const int z1 = Clamp(vz + 1, 0, grid.nVoxels[2] - 1);

    const float *row00 = density + static_cast<std::size_t>(z0) * grid.sliceStride +
                         static_cast<std::size_t>(y0) * grid.rowStride;
    const float *row10 = density + static_cast<std::size_t>(z0) * grid.sliceStride +
                         static_cast<std::size_t>(y1) * grid.rowStride;
    const float *row01 = density + static_cast<std::size_t>(z1) * grid.sliceStride +
                         static_cast<std::size_t>(y0) * grid.rowStride;
    const float *row11 = density + static_cast<std::size_t>(z1) * grid.sliceStride +
                         static_cast<std::size_t>(y1) * grid.rowStride;
    float d00 = Lerp(dx, row00[x0], row00[x1]);
    float d10 = Lerp(dx, row10[x0], row10[x1]);
    float d01 = Lerp(dx, row01[x0], row01[x1]);
    float d11 = Lerp(dx, row11[x0], row11[x1]);
    float d0 = Lerp(dy, d00, d10);
    float d1 = Lerp(dy, d01, d11);
    return Lerp(dz, d0, d1);
}

static float transmittance(float3 p0, float3 p1, const DensityGrid &grid, float sigma_t, const float density[]) {
    float rayT0, rayT1;
    Ray ray;
    ray.origin = p1;
    ray.dir = p0 - p1;

    // Find the parametric t range along the ray that is inside the volume.
    if (!IntersectP(ray, grid.pMin, grid.pMax, &rayT0, &rayT1))
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
        tau += stepDist * sigma_t * Density(pos, grid, density);
        pos = pos + dirStep;
        t += stepT;
    }

    return expf(-tau);
}

static float distanceSquared(float3 a, float3 b) {
    float3 d = a - b;
    return d.x * d.x + d.y * d.y + d.z * d.z;
}

static float raymarch(const float density[], const DensityGrid &grid, const Ray &ray) {
    float3 lightPos(-1.f, 4.f, 1.5f);
    float rayT0, rayT1;

    if (!IntersectP(ray, grid.pMin, grid.pMax, &rayT0, &rayT1))
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
        float d = Density(pos, grid, density);

        // terminate once attenuation is high
        float atten = expf(-tau);
        if (atten < .005f)
            break;

        // direct lighting
        float Li = lightIntensity / distanceSquared(lightPos, pos) *
                   transmittance(lightPos, pos, grid, sigma_a + sigma_s, density);
        L += stepDist * atten * d * sigma_s * (Li + Le);

        // update beam transmittance
        tau += stepDist * (sigma_a + sigma_s) * d;

        pos = pos + dirStep;
        t += stepT;
    }

    // Gamma correction
    return powf(L, 1.f / 2.2f);
}

void volume_serial(const float density[], int nVoxels[3], const float raster2camera[4][4], const float camera2world[4][4],
                   int width, int height, float image[]) {
    const DensityGrid grid = MakeDensityGrid(nVoxels);
    int offset = 0;
    for (int y = 0; y < height; ++y) {
        for (int x = 0; x < width; ++x, ++offset) {
            Ray ray;
            generateRay(raster2camera, camera2world, (float)x, (float)y, ray);
            image[offset] = raymarch(density, grid, ray);
        }
    }
}

static void volume_dynamic_chunks(const float density[], int nVoxels[3], const float raster2camera[4][4],
                                  const float camera2world[4][4], int width, int height, float image[], int threads) {
    if (threads <= 1 || width <= 0 || height <= 0) {
        volume_serial(density, nVoxels, raster2camera, camera2world, width, height, image);
        return;
    }

    const long long pixel_count = static_cast<long long>(width) * static_cast<long long>(height);
    int team_size = threads;
    if (pixel_count < team_size)
        team_size = static_cast<int>(pixel_count);
    if (team_size <= 1) {
        volume_serial(density, nVoxels, raster2camera, camera2world, width, height, image);
        return;
    }

    const DensityGrid grid = MakeDensityGrid(nVoxels);

    // Dynamic 64-pixel chunks retain contiguous writes while redistributing
    // work when neighboring rays have different march lengths.
    #pragma omp parallel for schedule(dynamic, 64) num_threads(team_size)
    for (long long index = 0; index < pixel_count; ++index) {
        const int y = static_cast<int>(index / width);
        const int x = static_cast<int>(index - static_cast<long long>(y) * width);
        Ray ray;
        generateRay(raster2camera, camera2world, static_cast<float>(x), static_cast<float>(y), ray);
        image[index] = raymarch(density, grid, ray);
    }
}

#include <cstring>
#include "render_context.h"
extern "C" void run(RenderInput*c,float*image,int*ids,int threads){volume_dynamic_chunks(c->density,c->nvox,c->raster2camera,c->camera2world,c->width,c->height,image,threads);}
