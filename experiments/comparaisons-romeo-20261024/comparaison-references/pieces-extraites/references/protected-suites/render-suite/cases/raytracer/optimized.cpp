#include <cstring>
#include "render_context.h"
#include "rt_ispc.h"
extern "C" void run(RenderInput*c,float*image,int*ids,int threads){ispc::raytrace_ispc(c->width,c->height,c->baseWidth,c->baseHeight,c->raster2camera,c->camera2world,image,ids,(const ispc::LinearBVHNode*)c->nodes,(const ispc::Triangle*)c->triangles);}
