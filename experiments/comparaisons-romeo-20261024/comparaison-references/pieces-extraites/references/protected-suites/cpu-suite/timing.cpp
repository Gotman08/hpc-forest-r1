#include <chrono>
#include <omp.h>
using Run=void(*)(const void*,const void*,void*,int,int,int);
extern "C" double timed(Run f,const void*a,const void*b,void*c,int n,int parameter,int threads,int repetitions,int warmups){omp_set_dynamic(0);omp_set_num_threads(threads);for(int i=0;i<warmups;i++)f(a,b,c,n,parameter,threads);auto t=std::chrono::steady_clock::now();for(int i=0;i<repetitions;i++){f(a,b,c,n,parameter,threads);asm volatile("":::"memory");}return std::chrono::duration<double>(std::chrono::steady_clock::now()-t).count()/repetitions;}
