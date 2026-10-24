from pathlib import Path
import shutil,json,tarfile
R=Path(__file__).resolve().parent;U=R/'upstream/examples/cpu';P=R/'render-suite';P.mkdir(exist_ok=True)
for folder in ['aobench','volume_rendering','rt','deferred']:
    dest=P/'reference'/folder
    if not dest.exists():shutil.copytree(U/folder,dest)
(P/'include').mkdir(exist_ok=True);shutil.copyfile(R/'render_context.h',P/'include/render_context.h');shutil.copyfile(R/'render_driver.cpp',P/'render_driver.cpp');shutil.copyfile(R/'cpu-preflight/examples/common/tasksys.cpp',P/'reference/tasksys.cpp')
cases=[{'id':'aobench','folder':'aobench','ispc_file':'ao','n':512,'threads':4,'checks':[32,64],'performance':[[512,1],[512,4],[2048,40]],'cpus':40},
{'id':'volume','folder':'volume_rendering','ispc_file':'volume','n':896,'threads':4,'checks':[112,224],'performance':[[896,1],[896,4],[896,40]],'cpus':40},
{'id':'raytracer','folder':'rt','ispc_file':'rt','n':900,'threads':4,'checks':[112,224],'performance':[[900,1],[900,4],[900,40]],'cpus':40},
{'id':'deferred','folder':'deferred','ispc_file':'kernels','n':1280,'threads':4,'checks':[1280],'performance':[[1280,1],[1280,4]],'cpus':4}]
for c in cases:
    key=c['id'];d=P/'cases'/key/'src';d.mkdir(parents=True,exist_ok=True)
    name={'aobench':'ao_serial.cpp','volume':'volume_serial.cpp','raytracer':'rt_serial.cpp','deferred':'dynamic_c.cpp'}[key]
    src=(U/c['folder']/name).read_text()
    if key=='aobench':body='memset(image,0,size_t(c->width)*c->height*3*4);ao_serial(c->width,c->height,c->nsubsamples,image);'
    elif key=='volume':body='volume_serial(c->density,c->nvox,c->raster2camera,c->camera2world,c->width,c->height,image);'
    elif key=='raytracer':body='raytrace_serial(c->width,c->height,c->baseWidth,c->baseHeight,c->raster2camera,c->camera2world,image,ids,(const ispc::LinearBVHNode*)c->nodes,(const ispc::Triangle*)c->triangles);'
    else:body='auto input=(InputData*)c->deferred;if(!gMinMaxZTree)InitDynamicC(input);DispatchDynamicC(input,(Framebuffer*)c->frame);'
    (d/'candidate.cpp').write_text(src+'\n#include <cstring>\n#include "render_context.h"\nextern "C" void run(RenderInput*c,float*image,int*ids,int threads){'+body+'}\n')
    for variant in ['optimized','tasks']:
        if key=='deferred' and variant=='tasks':continue
        call={'aobench':('ao_ispc','c->width,c->height,c->nsubsamples,image'), 'volume':('volume_ispc','c->density,c->nvox,c->raster2camera,c->camera2world,c->width,c->height,image'),'raytracer':('raytrace_ispc','c->width,c->height,c->baseWidth,c->baseHeight,c->raster2camera,c->camera2world,image,ids,(const ispc::LinearBVHNode*)c->nodes,(const ispc::Triangle*)c->triangles'),'deferred':('RenderStatic','((InputData*)c->deferred)->header,((InputData*)c->deferred)->arrays,0,((Framebuffer*)c->frame)->r,((Framebuffer*)c->frame)->g,((Framebuffer*)c->frame)->b')}[key]
        sym=call[0]+('_tasks' if variant=='tasks' else '')
        text='#include <cstring>\n#include "render_context.h"\n#include "'+c['ispc_file']+'_ispc.h"\n'+('#include "deferred.h"\n' if key=='deferred' else '')+'extern "C" void run(RenderInput*c,float*image,int*ids,int threads){'+('memset(image,0,size_t(c->width)*c->height*3*4);' if key=='aobench' else '')+'ispc::'+sym+'('+call[1]+');}\n'
        (d.parent/(variant+'.cpp')).write_text(text)
(P/'cases.json').write_text(json.dumps(cases,indent=2));print(json.dumps(cases))
