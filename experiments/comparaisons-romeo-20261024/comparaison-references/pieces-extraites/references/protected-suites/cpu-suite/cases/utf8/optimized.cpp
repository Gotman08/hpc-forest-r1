#include <cstdint>
#include "simdutf8check.h"
extern "C" void run(const void*a,const void*b,void*c,int n,int p,int t){*(uint32_t*)c=validate_utf8_fast_avx((const char*)a,n);}
