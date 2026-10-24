#include <cstring>
#include "render_context.h"
#include "kernels_ispc.h"
#include "deferred.h"
extern "C" void run(RenderInput*c,float*image,int*ids,int threads){ispc::RenderStatic(((InputData*)c->deferred)->header,((InputData*)c->deferred)->arrays,0,((Framebuffer*)c->frame)->r,((Framebuffer*)c->frame)->g,((Framebuffer*)c->frame)->b);}
