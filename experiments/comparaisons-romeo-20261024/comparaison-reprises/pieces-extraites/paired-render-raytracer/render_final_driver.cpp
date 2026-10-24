#include <dlfcn.h>
#include <omp.h>
#include <sched.h>
#include <chrono>
#include <vector>
#include <fstream>
#include <string>
#include <stdexcept>
#include <cstring>
#include <cmath>
#include <algorithm>
#include <cstdio>
#include "render_context.h"
#include "rt_ispc.h"
#include "deferred.h"
using Fn=void(*)(RenderInput*,float*,int*,int);
static Fn load(const std::string&path){auto h=dlopen(path.c_str(),RTLD_NOW|RTLD_LOCAL);if(!h)throw std::runtime_error(dlerror());auto f=(Fn)dlsym(h,"run");if(!f)throw std::runtime_error("missing run");return f;}
template<class T> void read(std::ifstream&f,T*data,size_t count){f.read((char*)data,count*sizeof(T));if(!f)throw std::runtime_error("truncated scene file");}
static uint64_t digest(const void*data,size_t bytes){auto p=(const unsigned char*)data;uint64_t h=1469598103934665603ULL;for(size_t i=0;i<bytes;i++)h=(h^p[i])*1099511628211ULL;return h;}
int main(int argc,char**argv){try{
 if(argc!=8)throw std::runtime_error("root case library n seed threads bench|check");
 std::string root=argv[1],name=argv[2],binary=argv[3];int n=atoi(argv[4]),seed=atoi(argv[5]),threads=atoi(argv[6]);bool bench=std::string(argv[7])=="bench";
 cpu_set_t old,set;CPU_ZERO(&old);CPU_ZERO(&set);sched_getaffinity(0,sizeof(old),&old);for(int i=0,c=0;i<CPU_SETSIZE&&c<threads;i++)if(CPU_ISSET(i,&old)){CPU_SET(i,&set);c++;}sched_setaffinity(0,sizeof(set),&set);omp_set_dynamic(0);omp_set_num_threads(threads);
 RenderInput ctx{};ctx.nsubsamples=2;std::vector<float>density;std::vector<ispc::LinearBVHNode>nodes;std::vector<ispc::Triangle>triangles;InputData*input=nullptr;Framebuffer*frame=nullptr;
 if(name=="aobench"){ctx.width=ctx.height=n;ctx.nsubsamples=seed>=1000?4:seed==308?3:2;}
 else if(name=="volume"){
  std::ifstream camera(root+"/data/volume_rendering/camera.dat");camera>>ctx.baseWidth>>ctx.baseHeight;for(auto&row:ctx.raster2camera)for(auto&v:row)camera>>v;for(auto&row:ctx.camera2world)for(auto&v:row)camera>>v;if(!camera)throw std::runtime_error("camera read");
  ctx.width=n;ctx.height=int(double(n)*ctx.baseHeight/ctx.baseWidth);float ratio=float(ctx.baseWidth)/ctx.width;for(int i=0;i<4;i++){ctx.raster2camera[i][0]*=ratio;ctx.raster2camera[i][1]*=ratio;}
  std::ifstream vol(root+"/data/volume_rendering/density_lowres.vol");for(auto&d:ctx.nvox)vol>>d;density.resize(size_t(ctx.nvox[0])*ctx.nvox[1]*ctx.nvox[2]);for(auto&v:density)vol>>v;if(!vol)throw std::runtime_error("volume read");ctx.density=density.data();
  if(seed==308||seed>=1000)for(auto&v:density)v*=seed>=1000?(1.f+float(seed%19+1)*.001f):1.01f;
 } else if(name=="raytracer"){
  std::ifstream camera(root+"/data/rt/sponza.camera",std::ios::binary);read(camera,&ctx.baseWidth,1);read(camera,&ctx.baseHeight,1);read(camera,&ctx.camera2world[0][0],16);read(camera,&ctx.raster2camera[0][0],16);ctx.width=n;ctx.height=int(double(n)*ctx.baseHeight/ctx.baseWidth);
  std::ifstream tree(root+"/data/rt/sponza.bvh",std::ios::binary);unsigned count;read(tree,&count,1);nodes.resize(count);for(auto&node:nodes){read(tree,&node.bounds[0][0],6);read(tree,&node.offset,1);read(tree,&node.nPrimitives,1);read(tree,&node.splitAxis,1);read(tree,&node.pad,1);}read(tree,&count,1);triangles.resize(count);for(unsigned i=0;i<count;i++){for(int j=0;j<3;j++)read(tree,triangles[i].p[j],3);triangles[i].id=i+1;}ctx.nodes=nodes.data();ctx.triangles=triangles.data();if(seed==308||seed>=1000)ctx.camera2world[0][3]+=seed>=1000?float(seed%13+1)*.00003f:.0001f;
 } else if(name=="deferred"){
  input=CreateInputDataFromFile((root+"/data/deferred/data/pp1280x720.bin").c_str());if(!input)throw std::runtime_error("deferred data read");ctx.width=input->header.framebufferWidth;ctx.height=input->header.framebufferHeight;ctx.deferred=input;frame=new Framebuffer(ctx.width,ctx.height);ctx.frame=frame;
  for(int i=0;i<MAX_LIGHTS;i++)if(seed==308||seed>=1000){float factor=seed>=1000?(1.f-float(seed%17+1)*.001f):.98f;input->arrays.lightColor_x[i]*=factor;input->arrays.lightColor_y[i]*=factor;input->arrays.lightColor_z[i]*=factor;}
 } else throw std::runtime_error("unknown case");
 size_t pixels=size_t(ctx.width)*ctx.height,count=pixels*(name=="aobench"?3:1);std::vector<float>image(count+32,0),expected(count+32,0);std::vector<int>ids(pixels+32,0),expected_ids(pixels+32,0);std::vector<unsigned char>expected_rgb;
 auto immutable=[&](){uint64_t h=0;h^=digest(density.data(),density.size()*4);h^=digest(nodes.data(),nodes.size()*sizeof(nodes[0]));h^=digest(triangles.data(),triangles.size()*sizeof(triangles[0]));if(input)h^=digest(input->chunk,input->header.inputDataChunkSize);return h;};uint64_t original=immutable();
 auto reference=load(root+"/cases/"+name+"/naive.so");auto candidate=load(binary);
 reference(&ctx,expected.data(),expected_ids.data(),threads);
 if(frame){expected_rgb.resize(3*pixels);memcpy(expected_rgb.data(),frame->r,pixels);memcpy(expected_rgb.data()+pixels,frame->g,pixels);memcpy(expected_rgb.data()+2*pixels,frame->b,pixels);frame->clear();for(auto p:{frame->r,frame->g,frame->b})memset(p+pixels,0xa7,64);}
 std::fill(image.begin()+count,image.end(),7654321.f);std::fill(ids.begin()+pixels,ids.end(),7654321);
 candidate(&ctx,image.data(),ids.data(),threads);
 size_t errors=0;double maxerr=0,mse=0,mean=0;
 if(frame){for(size_t i=0;i<pixels;i++)for(int j=0;j<3;j++){auto p=j==0?frame->r:j==1?frame->g:frame->b;int err=abs(int(p[i])-int(expected_rgb[j*pixels+i]));maxerr=std::max(maxerr,double(err));if(err>1)errors++;}for(auto p:{frame->r,frame->g,frame->b})for(int i=0;i<64;i++)if(p[pixels+i]!=0xa7)errors++;}
 else for(size_t i=0;i<count;i++){double delta=image[i]-expected[i];double err=fabs(delta);maxerr=std::max(maxerr,err);mse+=delta*delta;mean+=delta;if(!std::isfinite(image[i])||(name!="aobench"&&err>5e-4+5e-4*fabs(expected[i])))errors++;}
 mse=sqrt(mse/count);mean/=count;if(name=="aobench"&&(mse>.06||fabs(mean)>.015))errors++;
 if(name=="raytracer")for(size_t i=0;i<pixels;i++)if(ids[i]!=expected_ids[i])errors++;
 for(size_t i=count;i<image.size();i++)if(image[i]!=7654321.f)errors++;for(size_t i=pixels;i<ids.size();i++)if(ids[i]!=7654321)errors++;
 bool input_ok=immutable()==original;if(!input_ok)errors++;
 double seconds=0;int reps=0;if(bench&&!errors){candidate(&ctx,image.data(),ids.data(),threads);auto t=std::chrono::steady_clock::now();candidate(&ctx,image.data(),ids.data(),threads);double dt=std::chrono::duration<double>(std::chrono::steady_clock::now()-t).count();reps=std::max(1,std::min(1000,int(ceil(.05/std::max(dt,1e-9)))));t=std::chrono::steady_clock::now();for(int i=0;i<reps;i++)candidate(&ctx,image.data(),ids.data(),threads);seconds=std::chrono::duration<double>(std::chrono::steady_clock::now()-t).count()/reps;}
 printf("{\"case_id\":\"%s\",\"n\":%d,\"width\":%d,\"height\":%d,\"seed\":%d,\"threads\":%d,\"correct\":%s,\"errors\":%zu,\"max_abs_error\":%.12g,\"rmse\":%.12g,\"mean_error\":%.12g,\"input_unchanged\":%s,\"seconds\":%.12g,\"repetitions\":%d,\"warmups\":2}\n",name.c_str(),n,ctx.width,ctx.height,seed,threads,errors?"false":"true",errors,maxerr,mse,mean,input_ok?"true":"false",seconds,reps);return errors?1:0;
 }catch(const std::exception&e){fprintf(stderr,"%s\n",e.what());return 70;}}
