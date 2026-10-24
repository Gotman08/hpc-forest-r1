#include <cstring>
#include "render_context.h"
#include "volume_ispc.h"
extern "C" void run(RenderInput*c,float*image,int*ids,int threads){ispc::volume_ispc(c->density,c->nvox,c->raster2camera,c->camera2world,c->width,c->height,image);}
