from pathlib import Path
import json,ast,re,shutil,tarfile
R=Path(__file__).resolve().parent;U=R/'upstream';P=R/'gpu-extra';P.mkdir(exist_ok=True)
api='extern "C" void run(const void*x,const void*k,const void*gy,void*out,void*scratch,int n,int h,int l,int ks)\n'
red=(U/'reduction_kernel.cu').read_text();red=red[:red.index('template <typename T, unsigned int blockSize, bool nIsPow2>')]+ '\n#endif\n'
(P/'reduction.cuh').write_text(red)
wrap='''{int count=n;int*input=(int*)x;int*temp=(int*)scratch;bool flip=false;
while(count>1){int blocks=(count+DIVISOR-1)/DIVISOR;CAP
int*dest=flip?(int*)scratch+n+32768:(int*)scratch;
LAUNCH
input=dest;count=blocks;flip=!flip;}
cudaMemcpyAsync(out,input,sizeof(int),cudaMemcpyDeviceToDevice);}
'''
for v in range(1,8):
    div=128 if v<=3 else 256;cap='blocks=std::min(blocks,1024);' if v==7 else ''
    kernel=f'reduce{v-1}<int'+(',128,false' if v==7 else ',128' if v>=5 else '')+'>'
    body=wrap.replace('DIVISOR',str(div)).replace('CAP',cap).replace('LAUNCH',kernel+'<<<blocks,128,128*sizeof(int)>>>(input,dest,count);')
    source='#include <cuda_runtime.h>\n#include <algorithm>\n'+red+api+body
    (P/f'reduction-{v}.cu').write_text(source)
sumabs='''#include <cuda_runtime.h>
#include <cub/block/block_reduce.cuh>
__global__ void absolute(const float*x,float*t,int n){for(size_t i=blockIdx.x*blockDim.x+threadIdx.x;i<n;i+=size_t(blockDim.x)*gridDim.x)t[i]=fabsf(x[i]);}
template<bool ABS> __global__ void sum(const float*x,float*y,int n){using BR=cub::BlockReduce<float,256>;__shared__ typename BR::TempStorage temp;float s=0;for(size_t i=blockIdx.x*blockDim.x+threadIdx.x;i<n;i+=size_t(blockDim.x)*gridDim.x)s+=ABS?fabsf(x[i]):x[i];float total=BR(temp).Sum(s);if(threadIdx.x==0)atomicAdd(y,total);}
'''
for v in [1,2]:
    body='{cudaMemsetAsync(out,0,4);'+('absolute<<<1024,256>>>((const float*)x,(float*)scratch,n);sum<false><<<1024,256>>>((float*)scratch,(float*)out,n);' if v==1 else 'sum<true><<<1024,256>>>((const float*)x,(float*)out,n);')+'}\n'
    (P/f'sumabs-{v}.cu').write_text(sumabs+api+body)
for v,source in [(1,'naive'),(2,'warptiling')]:
    text=(U/'CUDA_Kernels_S4ConvD/validations'/(source+'.py')).read_text();code=text.split('kernel_code = r"""',1)[1].split('"""',1)[0]
    if v==1:body='''{size_t size=size_t(n)*h*l;float*y=(float*)out;float*gx=y+size;float*gk=gx+size;
dwconv1d_fwd_naive<<<dim3((l+255)/256,h,n),256>>>((const float*)x,(const float*)k,y,n,h,l,ks);
dwconv1d_bwd_input_naive<<<dim3((l+255)/256,h,n),256>>>((const float*)gy,(const float*)k,gx,n,h,l,ks);
dwconv1d_bwd_kernel_naive<<<dim3((ks+255)/256,h,1),256>>>((const float*)gy,(const float*)x,gk,n,h,l,ks);}
'''
    else:body='''{size_t size=size_t(n)*h*l;float*y=(float*)out;float*gx=y+size;float*gk=gx+size;
cudaMemsetAsync(gk,0,size_t(h)*ks*4);
dwconv1d_fwd_smallL<<<dim3(n,h),32>>>((const float*)x,(const float*)k,y,n,h,l,ks);
dwconv1d_bwd_input_smallL<<<dim3(n,h),32>>>((const float*)gy,(const float*)k,gx,n,h,l,ks);
dwconv1d_bwd_weight_atomic_packed_smallL<<<dim3(h,(n+63)/64),128>>>((const float*)gy,(const float*)x,gk,n,h,l,ks,(n+63)/64);}
'''
    (P/f's4convd-{v}.cu').write_text('#include <cuda_runtime.h>\n'+code+api+body)
soft=(U/'2eecd4928cb733fb.code.txt').read_text();soft=soft[:soft.index('torch.manual_seed(0)')]
(P/'softmax-reference.py').write_text(soft)
naive=soft[soft.index('def naive_softmax'):soft.index('@triton.jit')].replace('naive_softmax','run')
cases=[{'id':'reduction','n':4194304,'h':0,'l':0,'k':0,'checks':[1,127,1024,65536],'variants':list(range(1,8)),'reps':50,'warmups':5,'source_status':'Current NVIDIA CUDA sample port; variants 5-7 use synchronized warp shuffles, not the historical implicit warp memory synchronization.'},
{'id':'sumabs','n':268435456,'h':0,'l':0,'k':0,'checks':[1,127,1024,1048576],'variants':[1,2],'reps':20,'warmups':5,'source_status':'Reconstruction of partial NVIDIA blog code; 1 GiB chosen explicitly, 256 threads, 1024 blocks, output reset included.'},
{'id':'s4convd','n':16384,'h':128,'l':48,'k':47,'checks':[1,17,64],'variants':[1,2],'reps':8,'warmups':3,'source_status':'Exact notebook CUDA kernels, adapted host calls, common random tensors; all three kernels plus output reset timed.'},
{'id':'softmax','n':4096,'h':0,'l':0,'k':0,'checks':[32,97,781],'variants':['naive','triton','torch'],'reps':0,'warmups':0,'source_status':'Official Triton tutorial; common triton.testing.do_bench timing including launch and allocation behavior.'}]
for c in cases:
    d=P/'cases'/c['id']/'src';d.mkdir(parents=True,exist_ok=True)
    if c['id']=='softmax':(d/'candidate.py').write_text('import torch\n\n'+naive)
    else:shutil.copyfile(P/(c['id']+'-1.cu'),d/'candidate.cu')
(P/'cases.json').write_text(json.dumps(cases,indent=2))
print(json.dumps(cases,indent=2))
