#include <cstring>
#include "render_context.h"
#include "ao_ispc.h"
extern "C" void run(RenderInput*c,float*image,int*ids,int threads){memset(image,0,size_t(c->width)*c->height*3*4);ispc::ao_ispc_tasks(c->width,c->height,c->nsubsamples,image);}
