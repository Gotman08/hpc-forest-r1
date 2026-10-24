/*
  Copyright (c) 2011-2023, Intel Corporation

  SPDX-License-Identifier: BSD-3-Clause
*/

#include <algorithm>
#include <assert.h>
#include <math.h>
#include <cstring>
#include <new>
#include <stddef.h>

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

static inline float3 Offset(float3 p, float3 pMin, float3 pMax) {
    return float3((p.x - pMin.x) / (pMax.x - pMin.x), (p.y - pMin.y) / (pMax.y - pMin.y),
                  (p.z - pMin.z) / (pMax.z - pMin.z));
}

struct DensityVolume {
    const float *data;
    int nVoxels[3];
    bool hasHalo;
    size_t rowStride;
    size_t planeStride;
};

// Create one replicated border cell on each side of the input volume. The
// caller includes this allocation and copy in the measured render call.
static bool prepareDensityHalo(const float density[], const int nVoxels[3], float **haloOut, size_t *rowStrideOut,
                               size_t *planeStrideOut) {
    *haloOut = nullptr;
    *rowStrideOut = 0;
    *planeStrideOut = 0;

    if (nVoxels[0] <= 0 || nVoxels[1] <= 0 || nVoxels[2] <= 0)
        return false;

    const size_t maxSize = static_cast<size_t>(-1);
    const size_t nx = static_cast<size_t>(nVoxels[0]);
    const size_t ny = static_cast<size_t>(nVoxels[1]);
    const size_t nz = static_cast<size_t>(nVoxels[2]);
    if (nx > maxSize / ny)
        return false;
    const size_t originalPlane = nx * ny;
    if (originalPlane > maxSize / nz || nx > maxSize / sizeof(float))
        return false;

    if (nx > maxSize - 2 || ny > maxSize - 2 || nz > maxSize - 2)
        return false;
    const size_t paddedX = nx + 2;
    const size_t paddedY = ny + 2;
    const size_t paddedZ = nz + 2;
    if (paddedX > maxSize / paddedY)
        return false;
    const size_t planeStride = paddedX * paddedY;
    if (planeStride > maxSize / paddedZ)
        return false;
    const size_t total = planeStride * paddedZ;
    if (total > maxSize / sizeof(float))
        return false;

    float *halo = new (std::nothrow) float[total];
    if (!halo)
        return false;

    for (size_t z = 0; z < paddedZ; ++z) {
        const size_t sourceZ = (z == 0) ? 0 : ((z == paddedZ - 1) ? nz - 1 : z - 1);
        for (size_t y = 0; y < paddedY; ++y) {
            const size_t sourceY = (y == 0) ? 0 : ((y == paddedY - 1) ? ny - 1 : y - 1);
            const float *sourceRow = density + (sourceZ * ny + sourceY) * nx;
            float *destinationRow = halo + z * planeStride + y * paddedX;
            destinationRow[0] = sourceRow[0];
            std::memcpy(destinationRow + 1, sourceRow, nx * sizeof(float));
            destinationRow[paddedX - 1] = sourceRow[nx - 1];
        }
    }

    *haloOut = halo;
    *rowStrideOut = paddedX;
    *planeStrideOut = planeStride;
    return true;
}

static inline float Density(float3 Pobj, float3 pMin, float3 pMax, const DensityVolume &volume) {
    if (!Inside(Pobj, pMin, pMax))
        return 0;
    // Compute voxel coordinates and offsets for _Pobj_
    float3 vox = Offset(Pobj, pMin, pMax);
    vox.x = vox.x * volume.nVoxels[0] - .5f;
    vox.y = vox.y * volume.nVoxels[1] - .5f;
    vox.z = vox.z * volume.nVoxels[2] - .5f;
    int vx = (int)(vox.x), vy = (int)(vox.y), vz = (int)(vox.z);
    float dx = vox.x - vx, dy = vox.y - vy, dz = vox.z - vz;

    float v000, v001, v010, v011, v100, v101, v110, v111;
    if (volume.hasHalo) {
        // Limit each base index to the halo's representable range. Its adjacent
        // padded cell supplies the clamped upper neighbor without another clamp.
        long long baseX = vx, baseY = vy, baseZ = vz;
        if (baseX < -1)
            baseX = -1;
        else if (baseX >= static_cast<long long>(volume.nVoxels[0]))
            baseX = static_cast<long long>(volume.nVoxels[0]) - 1;
        if (baseY < -1)
            baseY = -1;
        else if (baseY >= static_cast<long long>(volume.nVoxels[1]))
            baseY = static_cast<long long>(volume.nVoxels[1]) - 1;
        if (baseZ < -1)
            baseZ = -1;
        else if (baseZ >= static_cast<long long>(volume.nVoxels[2]))
            baseZ = static_cast<long long>(volume.nVoxels[2]) - 1;

        const size_t x0 = static_cast<size_t>(baseX + 1);
        const size_t x1 = x0 + 1;
        const size_t y0 = static_cast<size_t>(baseY + 1) * volume.rowStride;
        const size_t y1 = y0 + volume.rowStride;
        const size_t z0 = static_cast<size_t>(baseZ + 1) * volume.planeStride;
        const size_t z1 = z0 + volume.planeStride;
        v000 = volume.data[z0 + y0 + x0];
        v001 = volume.data[z0 + y0 + x1];
        v010 = volume.data[z0 + y1 + x0];
        v011 = volume.data[z0 + y1 + x1];
        v100 = volume.data[z1 + y0 + x0];
        v101 = volume.data[z1 + y0 + x1];
        v110 = volume.data[z1 + y1 + x0];
        v111 = volume.data[z1 + y1 + x1];
    } else {
        // Preserve the direct flat-index path if a halo cannot be represented
        // or allocated for an otherwise valid input volume.
        int nx = volume.nVoxels[0];
        int ny = volume.nVoxels[1];
        int x0 = Clamp(vx, 0, nx - 1), x1 = Clamp(vx + 1, 0, nx - 1);
        int y0 = Clamp(vy, 0, ny - 1), y1 = Clamp(vy + 1, 0, ny - 1);
        int z0 = Clamp(vz, 0, volume.nVoxels[2] - 1), z1 = Clamp(vz + 1, 0, volume.nVoxels[2] - 1);
        int row0 = y0 * nx, row1 = y1 * nx;
        int plane0 = z0 * nx * ny, plane1 = z1 * nx * ny;
        v000 = volume.data[plane0 + row0 + x0];
        v001 = volume.data[plane0 + row0 + x1];
        v010 = volume.data[plane0 + row1 + x0];
        v011 = volume.data[plane0 + row1 + x1];
        v100 = volume.data[plane1 + row0 + x0];
        v101 = volume.data[plane1 + row0 + x1];
        v110 = volume.data[plane1 + row1 + x0];
        v111 = volume.data[plane1 + row1 + x1];
    }

    // Keep the original trilinear interpolation order.
    float d00 = Lerp(dx, v000, v001);
    float d10 = Lerp(dx, v010, v011);
    float d01 = Lerp(dx, v100, v101);
    float d11 = Lerp(dx, v110, v111);
    float d0 = Lerp(dy, d00, d10);
    float d1 = Lerp(dy, d01, d11);
    return Lerp(dz, d0, d1);
}

static float transmittance(float3 p0, float3 p1, float3 pMin, float3 pMax, float sigma_t,
                           const DensityVolume &volume) {
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
        tau += stepDist * sigma_t * Density(pos, pMin, pMax, volume);
        pos = pos + dirStep;
        t += stepT;
    }

    return expf(-tau);
}

static float distanceSquared(float3 a, float3 b) {
    float3 d = a - b;
    return d.x * d.x + d.y * d.y + d.z * d.z;
}

static float raymarch(const DensityVolume &volume, const Ray &ray) {
    float rayT0, rayT1;
    float3 pMin(.3f, -.2f, .3f), pMax(1.8f, 2.3f, 1.8f);
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
        float d = Density(pos, pMin, pMax, volume);

        // terminate once attenuation is high
        float atten = expf(-tau);
        if (atten < .005f)
            break;

        // direct lighting
        float Li = lightIntensity / distanceSquared(lightPos, pos) *
                   transmittance(lightPos, pos, pMin, pMax, sigma_a + sigma_s, volume);
        L += stepDist * atten * d * sigma_s * (Li + Le);

        // update beam transmittance
        tau += stepDist * (sigma_a + sigma_s) * d;

        pos = pos + dirStep;
        t += stepT;
    }

    // Gamma correction
    return powf(L, 1.f / 2.2f);
}

void volume_serial(float density[], int nVoxels[3], const float raster2camera[4][4], const float camera2world[4][4],
                   int width, int height, float image[]) {
    DensityVolume volume;
    volume.data = density;
    volume.nVoxels[0] = nVoxels[0];
    volume.nVoxels[1] = nVoxels[1];
    volume.nVoxels[2] = nVoxels[2];
    volume.hasHalo = false;
    volume.rowStride = 0;
    volume.planeStride = 0;

    float *halo = nullptr;
    if (width > 0 && height > 0 &&
        prepareDensityHalo(density, nVoxels, &halo, &volume.rowStride, &volume.planeStride)) {
        volume.data = halo;
        volume.hasHalo = true;
    }

    int offset = 0;
    for (int y = 0; y < height; ++y) {
        for (int x = 0; x < width; ++x, ++offset) {
            Ray ray;
            generateRay(raster2camera, camera2world, (float)x, (float)y, ray);
            image[offset] = raymarch(volume, ray);
        }
    }

    delete[] halo;
}

#include "render_context.h"
extern "C" void run(RenderInput*c,float*image,int*ids,int threads){volume_serial(c->density,c->nvox,c->raster2camera,c->camera2world,c->width,c->height,image);}
