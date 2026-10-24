#include <cstdint>
#include "fastavxbase64.h"
extern "C" void run(const void*a,const void*b,void*c,int n,int p,int t){*(uint64_t*)c=chromium_base64_decode((char*)c+16,(const char*)a,n);}
