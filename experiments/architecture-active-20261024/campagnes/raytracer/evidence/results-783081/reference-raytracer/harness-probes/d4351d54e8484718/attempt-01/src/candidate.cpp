/*
  Copyright (c) 2010-2023, Intel Corporation

  SPDX-License-Identifier: BSD-3-Clause
*/

#ifdef _MSC_VER
#define _CRT_SECURE_NO_WARNINGS
#define NOMINMAX
#pragma warning(disable : 4244)
#pragma warning(disable : 4305)
#endif

#include <algorithm>
#include <stdint.h>

// Just enough of a float3 class to do what we need in this file.
#ifdef _MSC_VER
__declspec(align(16))
#endif
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
    float x, y, z;
    float pad; // match padding/alignment of ispc version
}
#ifndef _MSC_VER
__attribute__((aligned(16)))
#endif
;

struct Ray {
    float3 origin, dir, invDir;
    unsigned int dirIsNeg[3];
    float mint, maxt;
    int hitId;
};

// Declare these in a namespace so the mangling matches
namespace ispc {
struct Triangle {
    float p[3][4]; // extra float pad after each vertex
    int32_t id;
    int32_t pad[3]; // make 16 x 32-bits
};

struct LinearBVHNode {
    float bounds[2][3];
    int32_t offset; // primitives for leaf, second child for interior
    uint8_t nPrimitives;
    uint8_t splitAxis;
    uint16_t pad;
};
} // namespace ispc

using namespace ispc;

inline float3 Cross(const float3 &v1, const float3 &v2) {
    float v1x = v1.x, v1y = v1.y, v1z = v1.z;
    float v2x = v2.x, v2y = v2.y, v2z = v2.z;
    float3 ret;
    ret.x = (v1y * v2z) - (v1z * v2y);
    ret.y = (v1z * v2x) - (v1x * v2z);
    ret.z = (v1x * v2y) - (v1y * v2x);
    return ret;
}

inline float Dot(const float3 &a, const float3 &b) { return a.x * b.x + a.y * b.y + a.z * b.z; }

static void generateRay(const float raster2camera[4][4], const float camera2world[4][4], float x, float y, Ray &ray) {
    ray.mint = 0.f;
    ray.maxt = 1e30f;

    ray.hitId = 0;

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

    ray.invDir.x = 1.f / ray.dir.x;
    ray.invDir.y = 1.f / ray.dir.y;
    ray.invDir.z = 1.f / ray.dir.z;

    ray.dirIsNeg[0] = (ray.invDir.x < 0) ? 1 : 0;
    ray.dirIsNeg[1] = (ray.invDir.y < 0) ? 1 : 0;
    ray.dirIsNeg[2] = (ray.invDir.z < 0) ? 1 : 0;
}

static inline bool BBoxIntersect(const float bounds[2][3], const Ray &ray) {
    float3 bounds0(bounds[0][0], bounds[0][1], bounds[0][2]);
    float3 bounds1(bounds[1][0], bounds[1][1], bounds[1][2]);
    float t0 = ray.mint, t1 = ray.maxt;

    float3 tNear = (bounds0 - ray.origin) * ray.invDir;
    float3 tFar = (bounds1 - ray.origin) * ray.invDir;
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

    return (t0 <= t1);
}

inline bool TriIntersect(const Triangle &tri, Ray &ray) {
    const float p0x = tri.p[0][0], p0y = tri.p[0][1], p0z = tri.p[0][2];
    const float e1x = tri.p[1][0] - p0x;
    const float e1y = tri.p[1][1] - p0y;
    const float e1z = tri.p[1][2] - p0z;
    const float e2x = tri.p[2][0] - p0x;
    const float e2y = tri.p[2][1] - p0y;
    const float e2z = tri.p[2][2] - p0z;

    const float dirX = ray.dir.x, dirY = ray.dir.y, dirZ = ray.dir.z;
    const float s1x = dirY * e2z - dirZ * e2y;
    const float s1y = dirZ * e2x - dirX * e2z;
    const float s1z = dirX * e2y - dirY * e2x;
    const float divisor = s1x * e1x + s1y * e1y + s1z * e1z;

    if (divisor == 0.)
        return false;
    const float invDivisor = 1.f / divisor;

    // Compute first barycentric coordinate
    const float dx = ray.origin.x - p0x;
    const float dy = ray.origin.y - p0y;
    const float dz = ray.origin.z - p0z;
    const float b1 = (dx * s1x + dy * s1y + dz * s1z) * invDivisor;
    if (b1 < 0. || b1 > 1.)
        return false;

    // Compute second barycentric coordinate
    const float s2x = dy * e1z - dz * e1y;
    const float s2y = dz * e1x - dx * e1z;
    const float s2z = dx * e1y - dy * e1x;
    const float b2 = (dirX * s2x + dirY * s2y + dirZ * s2z) * invDivisor;
    if (b2 < 0. || b1 + b2 > 1.)
        return false;

    // Compute _t_ to intersection point
    const float t = (e2x * s2x + e2y * s2y + e2z * s2z) * invDivisor;
    if (t < ray.mint || t > ray.maxt)
        return false;

    ray.maxt = t;
    ray.hitId = tri.id;
    return true;
}

bool BVHIntersect(const LinearBVHNode nodes[], const Triangle tris[], Ray &r) {
    Ray ray = r;
    bool hit = false;
    // Follow ray through BVH nodes to find primitive intersections
    int todoOffset = 0, nodeNum = 0;
    int todo[64];

    while (true) {
        // Check ray against BVH node
        const LinearBVHNode &node = nodes[nodeNum];
        if (BBoxIntersect(node.bounds, ray)) {
            unsigned int nPrimitives = node.nPrimitives;
            if (nPrimitives > 0) {
                // Intersect ray with primitives in leaf BVH node
                unsigned int primitivesOffset = node.offset;
                for (unsigned int i = 0; i < nPrimitives; ++i) {
                    if (TriIntersect(tris[primitivesOffset + i], ray))
                        hit = true;
                }
                if (todoOffset == 0)
                    break;
                nodeNum = todo[--todoOffset];
            } else {
                // Put far BVH node on _todo_ stack, advance to near node
                if (r.dirIsNeg[node.splitAxis]) {
                    todo[todoOffset++] = nodeNum + 1;
                    nodeNum = node.offset;
                } else {
                    todo[todoOffset++] = node.offset;
                    nodeNum = nodeNum + 1;
                }
            }
        } else {
            if (todoOffset == 0)
                break;
            nodeNum = todo[--todoOffset];
        }
    }
    r.maxt = ray.maxt;
    r.hitId = ray.hitId;

    return hit;
}

void raytrace_serial(int width, int height, int baseWidth, int baseHeight, const float raster2camera[4][4],
                     const float camera2world[4][4], float image[], int id[], const LinearBVHNode nodes[],
                     const Triangle triangles[]) {
    float widthScale = float(baseWidth) / float(width);
    float heightScale = float(baseHeight) / float(height);

    for (int y = 0; y < height; ++y) {
        for (int x = 0; x < width; ++x) {
            Ray ray;
            generateRay(raster2camera, camera2world, x * widthScale, y * heightScale, ray);
            BVHIntersect(nodes, triangles, ray);

            int offset = y * width + x;
            image[offset] = ray.maxt;
            id[offset] = ray.hitId;
        }
    }
}

#include <cstring>
#include "render_context.h"
extern "C" void run(RenderInput*c,float*image,int*ids,int threads){raytrace_serial(c->width,c->height,c->baseWidth,c->baseHeight,c->raster2camera,c->camera2world,image,ids,(const ispc::LinearBVHNode*)c->nodes,(const ispc::Triangle*)c->triangles);}
