#pragma once
struct RenderInput {
 int width,height,baseWidth,baseHeight,nsubsamples;
 int nvox[3];
 float raster2camera[4][4],camera2world[4][4];
 float*density;
 const void*nodes;
 const void*triangles;
 void*deferred;
 void*frame;
};
// All scene and camera data are read-only. The output buffers are writable.
// AO: image has 3*width*height floats; volume/RT: width*height floats.
// RT: ids has width*height int32; deferred writes its Framebuffer channels.
extern "C" void run(RenderInput*,float*image,int*ids,int threads);
