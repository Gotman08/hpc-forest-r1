"""Join the 62 documentary observations to independently remeasured programs.
No missing observation is imputed and no timing is normalized by peak hardware.
"""
from pathlib import Path
import json,statistics as st,math,csv,re,sys,hashlib,datetime
R=Path(__file__).resolve().parent
def read(name,default=None):
    p=R/name
    return json.loads(p.read_text(encoding='utf8')) if p.exists() else default
FILES={'gpu':'gpu-final-results.json','cpu':'cpu-final-results.json','extra':'extra-final-results.json','render':'render-final-results.json','clang':'clang-final-results.json'}
groups={k:read(v,[]) for k,v in FILES.items()}
def sample(group,key,variant,n,threads,pattern=0):
    result=[]
    for row in groups[group]:
        m=row.get('measurement',{})
        if row.get('diagnostic') or row.get('exit_code')!=0 or m.get('correct') is not True:continue
        if group=='clang' and row['block']==0:continue
        if row['case_id']!=key or str(row['variant'])!=variant:continue
        if m.get('n')!=n or (threads is not None and m.get('threads')!=threads) or m.get('pattern',0)!=pattern:continue
        seconds=m.get('seconds',m.get('latency_ms',0)/1000)
        if seconds>0:result.append({**m,'seconds':seconds,'block':row['block']})
    return result
def describe(rows,aggregation='median'):
    if not rows:return None
    x=[r['seconds'] for r in rows];v={'median':st.median,'mean':st.mean,'min':min}[aggregation](x)
    return {'seconds':v,'count':len(x),'median':st.median(x),'mean':st.mean(x),'min':min(x),'max':max(x),'cv_pct':100*st.stdev(x)/st.mean(x) if len(x)>1 else 0,'max_abs_error':max(r.get('max_abs_error',0) for r in rows),'input_hashes':sorted({r['input_sha256'] for r in rows if r.get('input_sha256')}),'affinity':sorted({tuple(r.get('affinity',[])) for r in rows})}
def ratio_range(a,b):
    b={r['block']:r['seconds'] for r in b};ratios=[r['seconds']/b[r['block']] for r in a if r['block'] in b]
    return [min(ratios),max(ratios)] if ratios else None
ENGINES={};TRIALS=[];ATTEMPTS=[]
for p in sorted((R/'campaigns').iterdir()):
    fs=list(p.glob('results/results-*/results.json'))
    if not fs:continue
    d=json.loads(fs[0].read_text());selected=d.get('best_confirmed') or {};g=d.get('final_g_confirmation') or {};plan=read('campaigns/'+p.name+'/plan.json',{})
    e={'case_id':p.name,'job':d['job_id'],'pipeline_complete':d.get('pipeline_complete',False),'error':d.get('error'),'verification':d.get('verification'),'winner_id':selected.get('experiment_id'),'selected_commit':selected.get('commit'),'final_g_commit':(g.get('outcome') or {}).get('commit'),'final_g_confirmed':g.get('status')=='confirmed','model':d.get('model'),'effort':d.get('effort'),'target_seconds':d.get('target_seconds'),'timing':d.get('timing'),'trial_count':len(d.get('trials',[])),'source_sha256':plan.get('source_sha256'),'naive_retained':selected.get('experiment_id','').startswith('baseline')}
    e['naive_retained']=bool(selected.get('is_baseline',e['naive_retained']))
    e['reference_seconds']=selected.get('reference_seconds')
    e['selected_objective_seconds']=selected.get('mean_seconds')
    e['final_g_objective_seconds']=(g.get('outcome') or {}).get('mean_seconds')
    for ordinal,t in enumerate(d.get('trials',[]),1):
        mission=json.loads(t.get('mission') or '{}');result=json.loads(t.get('result') or '{}')
        TRIALS.append({'case_id':d['subject'].removeprefix('reference-'),'campaign_directory':p.name,'ordinal':ordinal,'id':t['id'],'role':t['role'],'state':t['state'],'status':result.get('status'),'seconds':result.get('mean_seconds'),'commit':result.get('commit'),'hypothesis':mission.get('hypothesis'),'transformations':mission.get('transformations'),'reason':result.get('reason'),'parent':mission.get('base_commit'),'source_ids':mission.get('sources',[])})
    logical=d['subject'].removeprefix('reference-');e['case_id']=logical;e['campaign_directory']=p.name
    ATTEMPTS.append(e);ENGINES[logical]=e
ispc={'AO':('aobench',512),'BINOMIAL':('binomial',131072),'BLACKSCHOLES':('blackscholes',131072),'DEFERRED':('deferred',1280),'MANDELBROT':('mandelbrot',1024),'PERLIN':('noise',768),'RAYTRACER':('raytracer',900),'STENCIL':('stencil3d',256),'VOLUME':('volume',896)}
notes={
'aobench':'ISPC 1.32.0 courant, pas la version historique. Scène et nombre de rayons conservés ; générateurs aléatoires natifs différents. Contrôle image RMSE ≤0,06 et biais moyen ≤0,015 ; revue du candidat confirmant la conservation du nombre de rayons.',
'binomial':'ISPC 1.32.0 courant. 128k=131072 et 2M=2097152 ; constantes originales pour le chronométrage, options variées pour la correction. GCC 14.2 contre ISPC LLVM 23.1.2/AVX-512. Le code conserve la convention historique de 63 transitions.',
'blackscholes':'ISPC 1.32.0 courant. 128k=131072 et 2M=2097152 ; constantes originales au chronométrage et entrées variées aux contrôles. GCC 14.2 contre ISPC LLVM 23.1.2/AVX-512.',
'deferred':'ISPC 1.32.0 ; fichier fourni pp1280x720.bin. Frame entière, RGB contrôlé à ±1 niveau. La hiérarchie de profondeur dynamique est recalculée à chaque rendu.',
'mandelbrot':'Exemple ISPC courant : 1536×1024 pixels, 512 itérations maximum. La publication ne précise pas la taille. Même compte entier par pixel.',
'noise':'Exemple ISPC courant : 768×768, bornes [-10,10], 8 octaves. La publication ne précise pas la taille. Tolérance absolue et relative 5e-5.',
'raytracer':'Exemple ISPC courant : Sponza 900×900 ; scène et BVH fournis. Identifiants des triangles exacts, profondeur avec tolérance 5e-4 absolue et relative.',
'stencil3d':'Exemple ISPC courant : 256³, 6 étapes, deux grilles contrôlées. Entrées aléatoires communes ; remise à zéro/copier la grille incluse dans tous les temps. Taille historique non précisée.',
'volume':'Exemple ISPC courant : caméra 896×1184 et density_lowres.vol. Taille historique non précisée. Même ray marching ; tolérance 5e-4 absolue et relative. Référence ISPC limitée aux dimensions multiples de 4 : les contrôles 96×126 et 128×169, hors précondition, plantent. Forest et le naïf y passent. Audit séparé sur tailles admissibles 224×296 et 336×444.',
'popcount':'Boucle dépendante uint32 avec débordement modulaire, 1000 valeurs×100 passages. Le temps est celui du lot complet. Même code source pour les compilateurs ; version historique non précisée.',
'argmin':'8192 int32 ; premier indice en cas d’égalité. Référence du dépôt courant : bloc 2048, contre 256 dans l’article. Compilation GCC 14.2 -O3 -march=native.',
'base64':'Image Lena fournie : 141020 octets encodés, 105764 décodés ; résultat exact. Deux erreurs d’accès aux outils pendant la recherche ; Forest a conservé le naïf scalaire.',
'utf8':'Générateur déterministe de même distribution de longueurs, pas la même séquence libc historique. Le naïf original est incorrect sur certaines chaînes malformées ; ses temps concernent uniquement du texte valide. Forest part de sa version corrigée. Contrôles supplémentaires exhaustifs et aléatoires séparés.',
'gemm_cpu':'Reconstitution des extraits de l’article ; tuile intérieure fixée à 16, non précisée dans la source. FP32, 1024², 8 cœurs physiques ROMEO contre 8 threads logiques historiques. GCC 14.2 strict contre Clang 14 fast-math historique ; pas une reproduction exacte.',
'sgemm':'Sources SGEMM_CUDA figées ; M=N=K=4096 FP32, alpha=0,5 beta=3. CUDA 12.6.3, -O3 -arch=sm_90 ; oracle cuBLAS sans TF32. Même calcul sur GH200 pour tous les candidats.',
'reduction':'Port actuel du sample NVIDIA ; variantes 5–7 utilisent des shuffles synchronisés, pas le code G80 inchangé. 2^22 int32, 128 threads de référence, réduction complète multi-passes ; entiers bornés [-5,5].',
'transpose':'Sources NVIDIA : 1024² FP32. Même mesure ROMEO réutilisée pour les deux matériels publiés ; il ne s’agit pas de deux réplications indépendantes.',
'stencil_y':'Sources NVIDIA : grille 64³, halo périodique de période 63, coefficients 63×[4/5,-1/5,4/105,-1/280]. Même calcul et oracle sur GH200.',
'softmax':'Tutoriel Triton courant, torch 2.9.1+cu126 et Triton 3.5.1. FP32 4096². Même triton.testing.do_bench pour tous, allocations/lancements inclus, compilation JIT préchauffée.',
'sumabs':'Reconstitution de l’extrait NVIDIA ; 1 GiB exactement (268435456 float), 256 threads et 1024 blocs de référence. Nombre historique exact non établi. Remise à zéro de la sortie incluse ; oracle FP64, rtol 2e-4.',
's4convd':'Kernels CUDA des notebooks, B=16384 H=128 L=48 K=47. Entrées aléatoires communes, distinctes des projections du modèle publié. Forward, gradient entrée, gradient poids et remise à zéro chronométrés ensemble. Pas de mesure d’epoch.'}
missing={
'gpu_bvh_traversal':'Scène APEX Destruction exacte (12486 objets, 73704 paires) non fournie ; article contenant des extraits, pas un programme complet prêt à rejouer. Aucun speedup inventé sur une scène substituée.',
'gpu_bvh_hierarchy':'Codes Morton triés de la scène publiée et programme complet manquants. Une autre scène ne reproduirait pas ce point de mesure.',
'gpu_s4convd_epoch':'Données CSV et état complet du modèle/entraînement non disponibles dans les éléments fournis ; les kernels ont été testés séparément, sans extrapoler leur gain à l’epoch.',
'CPU_MIT_PYTHON_AVX':'Version optimisée complète et entrées exactes de la démonstration MIT non fournies. Les slides et une reproduction tierce ne suffisent pas à rejouer exactement le programme annoncé. Aucun temps extrapolé.',
'CPU_MIT_C_AVX':'Version AVX complète de la démonstration MIT et entrées exactes non fournies. Le GEMM FP32 1024² mesuré ailleurs ne remplace pas ce GEMM FP64 4096².'}
def mapping(id):
    group='cpu';base='naive';opt='optimized';threads=1;pattern=0;agg='median'
    if id.startswith('CPU_ISPC_'):
        family,nt=id.removeprefix('CPU_ISPC_').rsplit('_',1);key,n=ispc[family];threads=int(nt[:-1]);group='render' if key in ['aobench','volume','raytracer','deferred'] else 'cpu'
        if threads==40 and key in ['aobench','binomial','blackscholes']:n=2048 if key=='aobench' else 2097152
        opt='tasks' if threads>1 and key!='deferred' else 'optimized'
    elif id.startswith('CPU_POPCOUNT'):key,n='popcount',1000;group='clang' if id.endswith('CLANG') else 'cpu'
    elif id.startswith('CPU_BASE64'):key,n='base64',141020;base='chromium' if id.endswith('CHROMIUM') else 'naive'
    elif id.startswith('CPU_UTF8'):key,n='utf8',65536;agg='min' if id.endswith('BEST') else 'mean'
    elif id.startswith('CPU_ARGMIN'):key,n='argmin',8192;pattern=int(id.endswith('DECREASING'))
    elif id.startswith('CPU_BOEHM'):key,n,threads='gemm_cpu',1024,8;base='naive_o0' if 'DEFAULT' in id else 'naive';opt='reorder' if id.endswith('REORDER') else 'tiling' if id.endswith('TILING') else 'optimized'
    elif id.startswith('gpu_sgemm'):group,key,n,threads,base,opt='gpu','sgemm',4096,None,'ref-1','ref-'+('0' if id.endswith('cublas') else str(int(id.rsplit('_',1)[1])))
    elif id.startswith('gpu_reduce'):group,key,n,threads,base,opt='extra','reduction',4194304,None,'ref-1','ref-'+str(int(id.rsplit('_',1)[1]))
    elif id.startswith('gpu_transpose'):group,key,n,threads,base,opt='gpu','transpose',1024,None,'ref-1','ref-2'
    elif id=='gpu_stencil_y':group,key,n,threads,base,opt='gpu','stencil_y',64,None,'ref-1','ref-2'
    elif id=='gpu_softmax_triton':group,key,n,threads,base,opt='extra','softmax',4096,None,'ref-naive','ref-triton'
    elif id=='gpu_sum_abs_fusion':group,key,n,threads,base,opt='extra','sumabs',268435456,None,'ref-1','ref-2'
    elif id=='gpu_s4convd_kernels':group,key,n,threads,base,opt='extra','s4convd',16384,None,'ref-1','ref-2'
    else:raise ValueError(id)
    return group,key,n,threads,pattern,base,opt,agg
w=read('workbook.json');conditions={r[0]:r for r in w[1]['data'][7:] if r and r[0]};ROWS=[]
for original in w[0]['data'][7:]:
    id,label,metric,unit,before,after,computed,declared,hardware,input_text,family,url=original
    row={'id':id,'label':label,'family':family,'published_speedup':declared if declared is not None else computed,'published_computed_speedup':computed,'published_stated_speedup':declared,'published_metric':metric,'published_unit':unit,'published_before':before,'published_after':after,'published_hardware':hardware,'published_input':input_text,'source':url,'source_conditions':conditions.get(id)}
    if id in missing:row.update(status='Non exécuté — données/source manquantes',notes=missing[id],case_id=None);ROWS.append(row);continue
    group,key,n,threads,pattern,base,opt,agg=mapping(id);row.update(group=group,case_id=key,n=n,threads=threads,pattern=pattern,baseline_variant=base,reference_variant=opt,aggregation=agg,hardware='NVIDIA GH200 120 Go + CPU Grace ARM' if group in ['gpu','extra'] else 'AMD EPYC 9654 ; cœurs physiques, AVX-512',compiler='Clang 17.0.6' if group=='clang' else 'CUDA 12.6.3 / torch 2.9.1+cu126 / Triton 3.5.1' if group=='extra' else 'CUDA 12.6.3 -O3 sm_90' if group=='gpu' else 'GCC 14.2 -O3 -march=native ; références ISPC 1.32.0 LLVM 23.1.2 AVX-512',notes=notes[key],engine=ENGINES.get(key))
    if group=='clang':row['notes']+=' Forest a recherché sous GCC ; ses sources retenues sont ici recompilées inchangées avec Clang 17.0.6.'
    samples={name:sample(group,key,v,n,threads,pattern) for name,v in [('baseline',base),('reference',opt),('forest','selected'),('final_g','final_g')]}
    for name,ss in samples.items():row[name]=describe(ss,agg)
    if all(row[x] for x in ['baseline','reference','forest']):
        b,o,f=(row[x]['seconds'] for x in ['baseline','reference','forest']);row.update(reference_speedup=b/o,forest_speedup=b/f,forest_vs_reference=o/f,reference_shift_pct=(b/o/row['published_speedup']-1)*100,forest_speedup_range=ratio_range(samples['baseline'],samples['forest']),reference_speedup_range=ratio_range(samples['baseline'],samples['reference']),forest_vs_reference_range=ratio_range(samples['reference'],samples['forest']))
        if row['final_g']:row['final_g_speedup']=b/row['final_g']['seconds']
        hashes=[{x.get('input_sha256') for x in samples[name]} for name in ['baseline','reference','forest']]
        row['same_input_hashes']=hashes[0]==hashes[1]==hashes[2] if None not in hashes[0] else None
        if row['same_input_hashes'] is False:raise ValueError('Different benchmark inputs for '+id)
        if row['same_input_hashes'] is True:
            by_block={r['block']:r['input_sha256'] for r in samples['baseline']}
            for label in ['reference','forest','final_g']:
                assert all(by_block[r['block']]==r['input_sha256'] for r in samples[label]),(id,label,'input differs within block')
        if row['engine'] and row['engine']['naive_retained']:row['status']='Naïf conservé — erreurs de recherche'
        else:
            lo,hi=row['forest_vs_reference_range'];row['status']='Forest plus rapide à chaque répétition' if lo>1 else 'Référence plus rapide à chaque répétition' if hi<1 else 'Écart dans la variabilité observée'
        if key=='utf8':row['status']+=' ; naïf historique invalide hors texte valide'
    else:row['status']='Mesure finale en cours'
    ROWS.append(row)
RAW=[]
for group,rows in groups.items():
    for row in rows:
        m=row.get('measurement',{});RAW.append({'group':group,'case_id':row['case_id'],'variant':row['variant'],'block':row['block'],'diagnostic':row.get('diagnostic',False),'n':m.get('n'),'seed':m.get('seed'),'threads':m.get('threads'),'pattern':m.get('pattern'),'seconds':m.get('seconds',m.get('latency_ms',0)/1000) or None,'correct':m.get('correct'),'exit_code':row.get('exit_code'),'max_abs_error':m.get('max_abs_error'),'rmse':m.get('rmse'),'input_sha256':m.get('input_sha256'),'error':row.get('error',m.get('error'))})
summary={'observations':len(ROWS),'measured':sum('forest_speedup' in r for r in ROWS),'unavailable':len(missing),'pending':sum(r['status']=='Mesure finale en cours' for r in ROWS),'engine_cases':len(ENGINES),'final_records':len(RAW),'final_failures':[x for x in RAW if x['correct'] is not True], 'generated_at':datetime.datetime.now(datetime.timezone.utc).isoformat()}
DATA={'summary':summary,'rows':ROWS,'measurements':RAW,'engines':list(ENGINES.values()),'attempts':ATTEMPTS,'trials':TRIALS,'sources':read('acquisition.json'),'utf8_audit':read('utf8-audit.json'),'volume_domain_audit':read('volume-domain-audit.json')}
(R/'analysis.json').write_text(json.dumps(DATA,indent=2,ensure_ascii=False),encoding='utf8')
fields=['id','label','published_speedup','reference_speedup','forest_speedup','forest_vs_reference','final_g_speedup','reference_shift_pct','status','published_hardware','hardware','compiler','published_input','n','threads','pattern','aggregation','baseline_variant','reference_variant','notes','source']
flat=[]
for row in ROWS:
    d={k:row.get(k) for k in fields}
    for name in ['baseline','reference','forest','final_g']:
        q=row.get(name) or {};d[name+'_ms']=q['seconds']*1000 if q.get('seconds') else None;d[name+'_repetitions']=q.get('count');d[name+'_cv_pct']=q.get('cv_pct')
    flat.append(d)
with (R/'comparison.csv').open('w',encoding='utf-8-sig',newline='') as f:
    writer=csv.DictWriter(f,fieldnames=list(flat[0]));writer.writeheader();writer.writerows(flat)
print(json.dumps({k:v for k,v in summary.items() if k!='final_failures'},ensure_ascii=False));print('failed records',len(summary['final_failures']))
