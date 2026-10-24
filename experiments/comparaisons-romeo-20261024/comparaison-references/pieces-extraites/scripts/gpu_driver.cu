#include <cuda_runtime.h>
#include <dlfcn.h>
#include <cstdio>
#include <cstdlib>
#include <cmath>
#include <cstring>
#include <vector>
#include <random>
#include <string>
#include <algorithm>

// Candidate API: input A, input B, output/in-out C, scratch, dimensions,
// and SGEMM scalars. All storage belongs to this protected harness.
using Run = void(*)(const float*,const float*,float*,float*,int,int,int,float,float);
using Ref = void(*)(int,int,const float*,const float*,float*,float*,int,int,int,float,float);
static void ck(cudaError_t e) { if(e!=cudaSuccess){fprintf(stderr,"CUDA: %s\n",cudaGetErrorString(e));exit(70);} }
static float* alloc(size_t n){float*p;ck(cudaMalloc(&p,(n+32)*sizeof(float)));return p;}

int main(int argc,char**argv){
  if(argc!=10){fprintf(stderr,"case reference.so candidate.so|REF variant n seed repetitions warmups check\n");return 2;}
  const int kind=atoi(argv[1]), variant=atoi(argv[4]), n=atoi(argv[5]), seed=atoi(argv[6]);
  const int reps=atoi(argv[7]),warm=atoi(argv[8]); const bool check=atoi(argv[9]);
  void* ref_lib=dlopen(argv[2],RTLD_NOW|RTLD_LOCAL);
  if(!ref_lib){fprintf(stderr,"%s\n",dlerror());return 70;}
  Ref reference=(Ref)dlsym(ref_lib,"reference_run");
  const bool use_ref=std::string(argv[3])=="REF";
  void* candidate_lib=use_ref?nullptr:dlopen(argv[3],RTLD_NOW|RTLD_LOCAL);
  if(!use_ref&&!candidate_lib){fprintf(stderr,"%s\n",dlerror());return 71;}
  Run candidate=use_ref?nullptr:(Run)dlsym(candidate_lib,"run");
  if(!reference||(!use_ref&&!candidate)){fprintf(stderr,"Missing entry point\n");return 71;}
  int m=n,k=n;
  size_t count=(kind==2)?64*64*64:size_t(n)*n;
  std::mt19937 rng(seed);
  std::vector<float>a(count+32),b(count+32),c(count+32),expected(count+32),got(count+32);
  for(size_t i=0;i<count;i++){
    a[i]=(int(rng()%9)-4)+0.01f*(rng()%5);
    b[i]=(int(rng()%9)-4)+0.01f*(rng()%5);
    c[i]=(int(rng()%9)-4)*0.1f;
  }
  std::fill(a.begin()+count,a.end(),7654321.0f);std::fill(b.begin()+count,b.end(),7654321.0f);
  std::fill(c.begin()+count,c.end(),7654321.0f);
  float *da=alloc(count),*db=alloc(count),*dc=alloc(count),*de=alloc(count),*ds=alloc(count+65536);
  ck(cudaMemcpy(da,a.data(),a.size()*4,cudaMemcpyHostToDevice));ck(cudaMemcpy(db,b.data(),b.size()*4,cudaMemcpyHostToDevice));
  ck(cudaMemcpy(dc,c.data(),c.size()*4,cudaMemcpyHostToDevice));ck(cudaMemcpy(de,c.data(),c.size()*4,cudaMemcpyHostToDevice));
  ck(cudaMemset(ds,0,(count+65536)*4));
  const float alpha=0.5f,beta=3.0f;
  auto launch=[&](){if(use_ref) reference(kind,variant,da,db,dc,ds,n,m,k,alpha,beta);else candidate(da,db,dc,ds,n,m,k,alpha,beta);};
  double max_abs=0,max_rel=0;size_t errors=0;
  if(check){
    if(kind==0){reference(kind,0,da,db,de,ds,n,m,k,alpha,beta);ck(cudaDeviceSynchronize());ck(cudaMemcpy(expected.data(),de,expected.size()*4,cudaMemcpyDeviceToHost));}
    else if(kind==1){for(int r=0;r<n;r++)for(int col=0;col<n;col++)expected[size_t(col)*n+r]=a[size_t(r)*n+col];}
    else if(kind==2){
      const double co[4]={4.0/5*63,-1.0/5*63,4.0/105*63,-1.0/280*63};
      for(int z=0;z<64;z++)for(int y=0;y<64;y++)for(int x=0;x<64;x++){
        double v=0;for(int r=1;r<=4;r++){int yp=y+r,ym=y-r;if(yp>=64)yp-=63;if(ym<0)ym+=63;v+=co[r-1]*(a[(z*64+yp)*64+x]-a[(z*64+ym)*64+x]);}
        expected[(z*64+y)*64+x]=v;
      }
    }
    launch();ck(cudaGetLastError());ck(cudaDeviceSynchronize());ck(cudaMemcpy(got.data(),dc,got.size()*4,cudaMemcpyDeviceToHost));
    for(size_t i=0;i<count;i++){
      double err=fabs(double(got[i])-expected[i]);max_abs=std::max(max_abs,err);max_rel=std::max(max_rel,err/std::max(1e-20,fabs(double(expected[i]))));
      double tol=kind==0?0.01:kind==1?0:5e-5+2e-6*fabs(expected[i]);
      if(!std::isfinite(got[i])||err>tol)errors++;
    }
    for(size_t i=count;i<got.size();i++)if(got[i]!=7654321.0f)errors++;
    ck(cudaMemcpy(got.data(),da,got.size()*4,cudaMemcpyDeviceToHost));if(memcmp(got.data(),a.data(),a.size()*4))errors++;
    ck(cudaMemcpy(got.data(),db,got.size()*4,cudaMemcpyDeviceToHost));if(memcmp(got.data(),b.data(),b.size()*4))errors++;
  }
  float ms=0;
  if(errors==0&&reps>0){
    ck(cudaMemcpy(dc,c.data(),c.size()*4,cudaMemcpyHostToDevice));
    for(int i=0;i<warm;i++)launch();ck(cudaDeviceSynchronize());
    cudaEvent_t start,end;ck(cudaEventCreate(&start));ck(cudaEventCreate(&end));
    ck(cudaEventRecord(start));for(int i=0;i<reps;i++)launch();ck(cudaEventRecord(end));ck(cudaEventSynchronize(end));
    ck(cudaGetLastError());ck(cudaEventElapsedTime(&ms,start,end));ms/=reps;
    ck(cudaEventDestroy(start));ck(cudaEventDestroy(end));
  }
  printf("{\"correct\":%s,\"case\":%d,\"variant\":%d,\"n\":%d,\"seed\":%d,\"errors\":%zu,\"max_abs_error\":%.12g,\"max_relative_error\":%.12g,\"latency_ms\":%.12g,\"repetitions\":%d,\"warmups\":%d}\n",errors?"false":"true",kind,variant,n,seed,errors,max_abs,max_rel,ms,reps,warm);
  cudaFree(da);cudaFree(db);cudaFree(dc);cudaFree(de);cudaFree(ds);
  return errors?1:0;
}
