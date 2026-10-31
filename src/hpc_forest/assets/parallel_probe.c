/* Diagnostic-only GNU OpenMP observer. Never linked into measured executables.
 * It accounts callback CPU time and subtracts intercepted runtime waits. This
 * is runtime evidence, not a semantic proof that work contributes to output.
 */
#define _GNU_SOURCE
#include <dlfcn.h>
#include <errno.h>
#include <fcntl.h>
#include <sched.h>
#include <stdatomic.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/file.h>
#include <sys/stat.h>
#include <sys/syscall.h>
#include <time.h>
#include <unistd.h>

#define MAX_TEAM 4096
struct sample { unsigned long tid; int team,index,cpu,end_cpu,affinity_count;
  uint64_t work,start,end; };
struct region { void (*fn)(void*); void *data; struct sample *rows; _Atomic int error; };
struct frame { uint64_t excluded; unsigned depth; };
static _Thread_local struct frame *current;
static int enabled;
static _Atomic unsigned region_count;
static const char *trace_path;
static uint64_t clock_ns(clockid_t id) { struct timespec t; clock_gettime(id,&t);
  return (uint64_t)t.tv_sec*1000000000ULL+t.tv_nsec; }
static uint64_t exclude_begin(struct frame *f) {
  return f && f->depth++ == 0 ? clock_ns(CLOCK_THREAD_CPUTIME_ID) : 0;
}
static void exclude_end(struct frame *f,uint64_t start) {
  if (f && --f->depth == 0) f->excluded += clock_ns(CLOCK_THREAD_CPUTIME_ID)-start;
}
static FILE *report(void) {
  if (!enabled) return NULL;
  int fd=open(trace_path,O_WRONLY|O_APPEND|O_CREAT|O_CLOEXEC|O_NOFOLLOW,0600);
  if (fd<0 || flock(fd,LOCK_EX)) _exit(70);
  FILE *out=fdopen(fd,"a"); if (!out) _exit(70); return out;
}
__attribute__((constructor)) static void init(void) {
  const char *target=getenv("FOREST_PARALLEL_BINARY");
  trace_path=getenv("FOREST_PARALLEL_TRACE");
  struct stat a,b;
  if (!target || !trace_path || stat(target,&a) || stat("/proc/self/exe",&b)
      || a.st_ino!=b.st_ino || a.st_dev!=b.st_dev) return;
  enabled=1; FILE *out=report();
  fputs("{\"schema\":\"forest-gomp-probe-v1\",\"loaded\":true}\n",out); fclose(out);
}
static void callback(void *opaque) {
  struct region *r=opaque;
  int (*thread_num)(void)=dlsym(RTLD_NEXT,"omp_get_thread_num");
  int (*team_size)(void)=dlsym(RTLD_NEXT,"omp_get_num_threads");
  if (!thread_num || !team_size) _exit(70);
  int index=thread_num();
  if (index<0 || index>=MAX_TEAM) { atomic_store(&r->error,1); r->fn(r->data); return; }
  struct sample *s=&r->rows[index];
  s->tid=syscall(SYS_gettid);s->index=index;s->team=team_size();s->cpu=sched_getcpu();
  long configured=sysconf(_SC_NPROCESSORS_CONF);
  if(configured<1) _exit(70);
  size_t set_size=CPU_ALLOC_SIZE(configured);
  cpu_set_t *set=CPU_ALLOC(configured);if(!set) _exit(70);CPU_ZERO_S(set_size,set);
  s->affinity_count=sched_getaffinity(0,set_size,set)==0 ? CPU_COUNT_S(set_size,set) : 0;
  CPU_FREE(set);
  struct frame frame={0}, *previous=current; current=&frame;
  s->start=clock_ns(CLOCK_MONOTONIC);
  uint64_t begin=clock_ns(CLOCK_THREAD_CPUTIME_ID);
  r->fn(r->data);
  uint64_t elapsed=clock_ns(CLOCK_THREAD_CPUTIME_ID)-begin;
  s->end=clock_ns(CLOCK_MONOTONIC);current=previous;s->end_cpu=sched_getcpu();
  s->work=elapsed>frame.excluded ? elapsed-frame.excluded : 0;
}
struct observation { struct region region; struct frame *outer;
  uint64_t excluded; const char *api; };
static int region_begin(struct observation *o,void (*fn)(void*),void *data,const char *api) {
  if (!enabled) return 0;
  unsigned sequence=atomic_fetch_add(&region_count,1);
  if(sequence>=512) {
    if(sequence==512) {FILE *out=report();fputs("{\"schema\":\"forest-gomp-limit-v1\"}\n",out);fclose(out);}
    return 0;
  }
  o->outer=current;o->excluded=exclude_begin(o->outer);o->api=api;
  o->region.fn=fn;o->region.data=data;
  o->region.rows=calloc(MAX_TEAM,sizeof(struct sample));atomic_init(&o->region.error,0);
  if (!o->region.rows) _exit(70);
  return 1;
}
static void region_end(struct observation *o) {
  FILE *out=report();
  fprintf(out,"{\"schema\":\"forest-gomp-region-v1\",\"api\":\"%s\",\"error\":%d,\"threads\":[",o->api,atomic_load(&o->region.error));
  int comma=0;
  for(int i=0;i<MAX_TEAM;i++) { struct sample *s=&o->region.rows[i]; if (!s->tid) continue;
    fprintf(out,"%s{\"tid\":%lu,\"index\":%d,\"team\":%d,\"cpu\":%d,\"end_cpu\":%d,\"affinity_count\":%d,\"work_cpu_ns\":%llu,\"start_ns\":%llu,\"end_ns\":%llu}",
      comma++?",":"",s->tid,s->index,s->team,s->cpu,s->end_cpu,s->affinity_count,
      (unsigned long long)s->work,(unsigned long long)s->start,(unsigned long long)s->end);
  }
  fputs("]}\n",out);fclose(out);free(o->region.rows);exclude_end(o->outer,o->excluded);
}
/* Combined constructs have their own public entry points in the GNU ABI.
 * Keep their bounds, scheduling arguments and flags intact. */
#define PARALLEL(name,decl,args,observed_args) \
 void name decl { typedef void (*type) decl; static _Atomic(type) cached; \
 type real=atomic_load(&cached);if(!real){real=dlsym(RTLD_NEXT,#name);if(!real)_exit(70);atomic_store(&cached,real);} \
 struct observation o; if(!region_begin(&o,fn,data,#name)){real args;return;} \
 real observed_args;region_end(&o); }
PARALLEL(GOMP_parallel,(void (*fn)(void*),void *data,unsigned threads,unsigned flags),
         (fn,data,threads,flags),(callback,&o.region,threads,flags))
#define PARALLEL_LOOP(kind) \
 PARALLEL(GOMP_parallel_loop_##kind, \
  (void (*fn)(void*),void *data,unsigned threads,long start,long end,long increment,long chunk,unsigned flags), \
  (fn,data,threads,start,end,increment,chunk,flags), \
  (callback,&o.region,threads,start,end,increment,chunk,flags))
PARALLEL_LOOP(static)
PARALLEL_LOOP(dynamic)
PARALLEL_LOOP(guided)
PARALLEL_LOOP(nonmonotonic_dynamic)
PARALLEL_LOOP(nonmonotonic_guided)
#define PARALLEL_RUNTIME(kind) \
 PARALLEL(GOMP_parallel_loop_##kind, \
  (void (*fn)(void*),void *data,unsigned threads,long start,long end,long increment,unsigned flags), \
  (fn,data,threads,start,end,increment,flags), \
  (callback,&o.region,threads,start,end,increment,flags))
PARALLEL_RUNTIME(runtime)
PARALLEL_RUNTIME(nonmonotonic_runtime)
PARALLEL_RUNTIME(maybe_nonmonotonic_runtime)
PARALLEL(GOMP_parallel_sections,
         (void (*fn)(void*),void *data,unsigned threads,unsigned count,unsigned flags),
         (fn,data,threads,count,flags),(callback,&o.region,threads,count,flags))
/* Split entry points and task-reduction data have different lifetimes/layouts.
 * Preserve their execution and classify unsupported observation as unscored. */
static void unsupported(const char *api) {
  if(!enabled)return;
  FILE *out=report();fprintf(out,"{\"schema\":\"forest-gomp-unsupported-v1\",\"api\":\"%s\"}\n",api);fclose(out);
}
#define UNSUPPORTED(name,decl,args) \
 void name decl {typedef void (*type) decl;static _Atomic(type) cached;type real=atomic_load(&cached); \
 if(!real){real=dlsym(RTLD_NEXT,#name);if(!real)_exit(70);atomic_store(&cached,real);} \
 unsupported(#name);real args;}
UNSUPPORTED(GOMP_parallel_start,(void (*fn)(void*),void *data,unsigned threads),(fn,data,threads))
#define SPLIT_LOOP(kind) \
 UNSUPPORTED(GOMP_parallel_loop_##kind##_start, \
 (void (*fn)(void*),void *data,unsigned threads,long start,long end,long increment,long chunk), \
 (fn,data,threads,start,end,increment,chunk))
SPLIT_LOOP(static)
SPLIT_LOOP(dynamic)
SPLIT_LOOP(guided)
UNSUPPORTED(GOMP_parallel_loop_runtime_start,
 (void (*fn)(void*),void *data,unsigned threads,long start,long end,long increment),
 (fn,data,threads,start,end,increment))
UNSUPPORTED(GOMP_parallel_sections_start,
 (void (*fn)(void*),void *data,unsigned threads,unsigned count),(fn,data,threads,count))
unsigned GOMP_parallel_reductions(void (*fn)(void*),void *data,unsigned threads,unsigned flags) {
  typedef unsigned (*type)(void (*)(void*),void*,unsigned,unsigned);
  static _Atomic(type) cached;type real=atomic_load(&cached);
  if(!real){real=dlsym(RTLD_NEXT,"GOMP_parallel_reductions");if(!real)_exit(70);atomic_store(&cached,real);}
  unsupported("GOMP_parallel_reductions");return real(fn,data,threads,flags);
}
#define WRAP_VOID(name,decl,args) \
 void name decl { struct frame *trace_frame=current;uint64_t stamp=exclude_begin(trace_frame); typedef void (*type) decl; static _Atomic(type) cached; \
 type real=atomic_load(&cached); if(!real) {real=dlsym(RTLD_NEXT,#name);if(!real)_exit(70);atomic_store(&cached,real);} \
 real args;exclude_end(trace_frame,stamp); }
#define WRAP_BOOL(name,decl,args) \
 _Bool name decl { struct frame *trace_frame=current;uint64_t stamp=exclude_begin(trace_frame); typedef _Bool (*type) decl; static _Atomic(type) cached; \
 type real=atomic_load(&cached);if(!real){real=dlsym(RTLD_NEXT,#name);if(!real)_exit(70);atomic_store(&cached,real);} \
 _Bool v=real args;exclude_end(trace_frame,stamp);return v; }
#define WRAP_UNSIGNED(name,decl,args) \
 unsigned name decl { struct frame *trace_frame=current;uint64_t stamp=exclude_begin(trace_frame);typedef unsigned (*type) decl;static _Atomic(type) cached; \
 type real=atomic_load(&cached);if(!real){real=dlsym(RTLD_NEXT,#name);if(!real)_exit(70);atomic_store(&cached,real);} \
 unsigned v=real args;exclude_end(trace_frame,stamp);return v; }
WRAP_VOID(GOMP_barrier,(void),())
WRAP_BOOL(GOMP_barrier_cancel,(void),())
WRAP_VOID(GOMP_loop_end,(void),())
WRAP_VOID(GOMP_loop_end_nowait,(void),())
WRAP_BOOL(GOMP_loop_end_cancel,(void),())
WRAP_VOID(GOMP_sections_end,(void),())
WRAP_VOID(GOMP_sections_end_nowait,(void),())
WRAP_BOOL(GOMP_sections_end_cancel,(void),())
WRAP_UNSIGNED(GOMP_sections_start,(unsigned count),(count))
WRAP_UNSIGNED(GOMP_sections_next,(void),())
WRAP_VOID(GOMP_taskwait,(void),())
WRAP_VOID(GOMP_taskgroup_end,(void),())
WRAP_VOID(GOMP_critical_start,(void),())
WRAP_VOID(GOMP_critical_end,(void),())
WRAP_VOID(GOMP_critical_name_start,(void **p),(p))
WRAP_VOID(GOMP_critical_name_end,(void **p),(p))
WRAP_VOID(GOMP_atomic_start,(void),())
WRAP_VOID(GOMP_atomic_end,(void),())
WRAP_VOID(GOMP_ordered_start,(void),())
WRAP_VOID(GOMP_ordered_end,(void),())
WRAP_BOOL(GOMP_single_start,(void),())
#define LOOP(kind) \
 WRAP_BOOL(GOMP_loop_##kind##_start,(long a,long b,long c,long d,long *e,long *f),(a,b,c,d,e,f)) \
 WRAP_BOOL(GOMP_loop_##kind##_next,(long *a,long *b),(a,b)) \
 WRAP_BOOL(GOMP_loop_nonmonotonic_##kind##_start,(long a,long b,long c,long d,long *e,long *f),(a,b,c,d,e,f)) \
 WRAP_BOOL(GOMP_loop_nonmonotonic_##kind##_next,(long *a,long *b),(a,b))
LOOP(dynamic)
LOOP(guided)
WRAP_BOOL(GOMP_loop_static_start,(long a,long b,long c,long d,long *e,long *f),(a,b,c,d,e,f))
WRAP_BOOL(GOMP_loop_static_next,(long *a,long *b),(a,b))
#define RUNTIME(kind) \
 WRAP_BOOL(GOMP_loop_##kind##_start,(long a,long b,long c,long *d,long *e),(a,b,c,d,e)) \
 WRAP_BOOL(GOMP_loop_##kind##_next,(long *a,long *b),(a,b))
RUNTIME(runtime)
RUNTIME(nonmonotonic_runtime)
RUNTIME(maybe_nonmonotonic_runtime)
