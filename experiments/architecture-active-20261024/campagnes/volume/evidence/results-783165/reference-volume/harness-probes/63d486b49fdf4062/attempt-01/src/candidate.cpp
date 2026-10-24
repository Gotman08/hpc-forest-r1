/*
  Copyright (c) 2011-2023, Intel Corporation

  SPDX-License-Identifier: BSD-3-Clause
*/

#include <algorithm>
#include <math.h>
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

static const float3 kVolumeMin(.3f, -.2f, .3f);
static const float3 kVolumeMax(1.8f, 2.3f, 1.8f);

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

struct DensityVolume {
    const float *data;
    int nVoxels[3];
    float coordinateScale[3];
    size_t rowStride;
    size_t planeStride;
};

static inline float Density(float3 Pobj, float3 pMin, float3 pMax, const DensityVolume &volume) {
    if (!Inside(Pobj, pMin, pMax))
        return 0;

    // Convert to voxel coordinates using factors prepared once per render call.
    float voxX = (Pobj.x - pMin.x) * volume.coordinateScale[0] - .5f;
    float voxY = (Pobj.y - pMin.y) * volume.coordinateScale[1] - .5f;
    float voxZ = (Pobj.z - pMin.z) * volume.coordinateScale[2] - .5f;
    int vx = (int)(voxX), vy = (int)(voxY), vz = (int)(voxZ);
    float dx = voxX - vx, dy = voxY - vy, dz = voxZ - vz;

    int nx = volume.nVoxels[0];
    int ny = volume.nVoxels[1];
    int x0 = Clamp(vx, 0, nx - 1), x1 = Clamp(vx + 1, 0, nx - 1);
    int y0 = Clamp(vy, 0, ny - 1), y1 = Clamp(vy + 1, 0, ny - 1);
    int z0 = Clamp(vz, 0, volume.nVoxels[2] - 1), z1 = Clamp(vz + 1, 0, volume.nVoxels[2] - 1);

    size_t row0 = static_cast<size_t>(y0) * volume.rowStride;
    size_t row1 = static_cast<size_t>(y1) * volume.rowStride;
    size_t plane0 = static_cast<size_t>(z0) * volume.planeStride;
    size_t plane1 = static_cast<size_t>(z1) * volume.planeStride;
    size_t sx0 = static_cast<size_t>(x0), sx1 = static_cast<size_t>(x1);

    float v000 = volume.data[plane0 + row0 + sx0];
    float v001 = volume.data[plane0 + row0 + sx1];
    float v010 = volume.data[plane0 + row1 + sx0];
    float v011 = volume.data[plane0 + row1 + sx1];
    float v100 = volume.data[plane1 + row0 + sx0];
    float v101 = volume.data[plane1 + row0 + sx1];
    float v110 = volume.data[plane1 + row1 + sx0];
    float v111 = volume.data[plane1 + row1 + sx1];

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
    float3 pMin = kVolumeMin, pMax = kVolumeMax;
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

    // Prepare scale factors and flat-layout strides once; Density performs no
    // allocation, copying, or per-sample coordinate divisions.
    volume.coordinateScale[0] = static_cast<float>(nVoxels[0]) / (kVolumeMax.x - kVolumeMin.x);
    volume.coordinateScale[1] = static_cast<float>(nVoxels[1]) / (kVolumeMax.y - kVolumeMin.y);
    volume.coordinateScale[2] = static_cast<float>(nVoxels[2]) / (kVolumeMax.z - kVolumeMin.z);
    volume.rowStride = static_cast<size_t>(nVoxels[0]);
    volume.planeStride = volume.rowStride * static_cast<size_t>(nVoxels[1]);

    int offset = 0;
    for (int y = 0; y < height; ++y) {
        for (int x = 0; x < width; ++x, ++offset) {
            Ray ray;
            generateRay(raster2camera, camera2world, (float)x, (float)y, ray);
            image[offset] = raymarch(volume, ray);
        }
    }
}

#include "render_context.h"
extern "C" void run(RenderInput*c,float*image,int*ids,int threads){volume_serial(c->density,c->nvox,c->raster2camera,c->camera2world,c->width,c->height,image);}
