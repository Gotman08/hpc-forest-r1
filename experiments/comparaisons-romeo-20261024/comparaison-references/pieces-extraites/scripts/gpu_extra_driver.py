from pathlib import Path
import os,sys,json,ctypes as ct,importlib.util,importlib.machinery
import torch
R=Path(__file__).resolve().parent
C={c['id']:c for c in json.loads((R/'cases.json').read_text())}
torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False
def module(path,name):
    loader=importlib.machinery.SourceFileLoader(name,str(path));spec=importlib.util.spec_from_loader(name,loader);m=importlib.util.module_from_spec(spec);sys.modules[name]=m;spec.loader.exec_module(m);return m
def run(name,binary,n,seed,bench):
    c=C[name];torch.manual_seed(seed);device='cuda';assert torch.cuda.current_stream().cuda_stream==0
    if name=='softmax':
        x=torch.randn((n,n),device=device,dtype=torch.float32);before=x.clone()
        if binary in ['naive','triton','torch']:
            ref=module(R/'softmax-reference.py','protected_reference')
            f={'naive':ref.naive_softmax,'triton':ref.softmax,'torch':lambda t:torch.softmax(t,dim=1)}[binary]
        else:f=module(Path(binary),'candidate_softmax').run
        expected=torch.softmax(x.double(),dim=1).float();y=f(x);torch.cuda.synchronize()
        error=(y-expected).abs();correct=bool(torch.allclose(y,expected,atol=1e-6,rtol=1e-5) and torch.equal(x,before))
        row={'case_id':name,'n':n,'seed':seed,'correct':correct,'max_abs_error':error.max().item()}
        if bench and correct:
            import triton.testing
            ms=triton.testing.do_bench(lambda:f(x),warmup=25,rep=100,return_mode='median')
            row.update(latency_ms=ms,seconds=ms/1000,gbps=2*x.numel()*x.element_size()/ms/1e6,metric='triton_do_bench_median_seconds')
        return row
    dll=ct.CDLL(str(Path(binary).resolve()),mode=os.RTLD_LOCAL);f=dll.run;f.argtypes=[ct.c_void_p]*5+[ct.c_int]*4;f.restype=None
    if name=='reduction':
        x=torch.randint(-5,6,(n,),device=device,dtype=torch.int32);k=torch.zeros(1,device=device);gy=k
        expected=x.sum(dtype=torch.int64).to(torch.int32).reshape(1);length=1;scratch=2*n+65536;dtype=torch.int32
    elif name=='sumabs':
        x=torch.randn(n,device=device);k=torch.zeros(1,device=device);gy=k
        expected=x.double().abs().sum().float().reshape(1);length=1;scratch=n+65536;dtype=torch.float32
    else:
        h,l,ks=c['h'],c['l'],c['k'];x=torch.randn((n,h,l),device=device)*.04;k=torch.randn((h,ks),device=device)*.02;gy=torch.randn_like(x)
        # Independent double-precision conv1d/autograd oracle; CPU memory is
        # not part of the measured path and TF32 is disabled explicitly.
        xd=x.double().requires_grad_();kd=k.double().requires_grad_()
        yy=torch.nn.functional.conv1d(xd,kd[:,None,:],padding=ks//2,groups=h)
        gx,gk=torch.autograd.grad(yy,(xd,kd),grad_outputs=gy.double())
        expected=torch.cat([yy.float().flatten(),gx.float().flatten(),gk.float().flatten()]).detach()
        del xd,kd,yy,gx,gk
        length=expected.numel();scratch=2*x.numel()+65536;dtype=torch.float32
    before=[a.clone() for a in [x,k,gy]]
    storage=torch.full((length+64,),12345,device=device,dtype=dtype);output=storage[:length];temp=torch.empty(scratch,device=device,dtype=dtype)
    invoke=lambda:f(x.data_ptr(),k.data_ptr(),gy.data_ptr(),output.data_ptr(),temp.data_ptr(),n,c['h'],c['l'],c['k'])
    invoke();torch.cuda.synchronize()
    delta=(output.double()-expected.double()).abs()
    if name=='reduction':good=output==expected
    elif name=='sumabs':good=delta<=2e-4*expected.abs()+.001
    else:
        tol=torch.full_like(expected,2e-5);tol[2*x.numel():]=.005
        good=delta<=tol+2e-4*expected.abs()
    errors=int((~good|~torch.isfinite(output)).sum().item());guards=bool(torch.all(storage[length:]==12345));immutable=all(torch.equal(a,b) for a,b in zip([x,k,gy],before))
    row={'case_id':name,'n':n,'h':c['h'],'l':c['l'],'k':c['k'],'seed':seed,'correct':errors==0 and guards and immutable,'errors':errors,'guards':guards,'input_unchanged':immutable,'max_abs_error':delta.max().item()}
    if bench and row['correct']:
        for _ in range(c['warmups']):invoke()
        torch.cuda.synchronize();start=torch.cuda.Event(enable_timing=True);end=torch.cuda.Event(enable_timing=True)
        start.record()
        for _ in range(c['reps']):invoke()
        end.record();end.synchronize();ms=start.elapsed_time(end)/c['reps']
        row.update(latency_ms=ms,seconds=ms/1000,repetitions=c['reps'],warmups=c['warmups'],metric='cuda_event_seconds')
    return row
if __name__=='__main__':
    row=run(sys.argv[1],sys.argv[2],int(sys.argv[3]),int(sys.argv[4]),sys.argv[5]=='bench');print(json.dumps(row));sys.exit(0 if row['correct'] else 1)
