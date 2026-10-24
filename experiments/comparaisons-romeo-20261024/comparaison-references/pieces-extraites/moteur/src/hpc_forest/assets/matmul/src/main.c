#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "params.h"

/* Synthetic training task. Integer-valued doubles keep the oracle exact. */
static void multiply(const double *a, const double *b, double *c, int n) {
    int i;
#if PARALLEL
    #pragma omp parallel for schedule(static, OMP_CHUNK)
#endif
    for (i = 0; i < n; ++i) {
#if LAYOUT
        for (int kk = 0; kk < n; kk += TILE) {
            const int end = kk + TILE < n ? kk + TILE : n;
            for (int k = kk; k < end; ++k) {
                const double value = a[i*n+k];
                for (int jj = 0; jj < n; jj += J_TILE) {
                    const int je = jj + J_TILE < n ? jj + J_TILE : n;
#if SIMD && defined(_MSC_VER)
                    #pragma loop(ivdep)
#elif SIMD
                    #pragma omp simd
#endif
                    for (int j = jj; j < je; ++j)
                        c[i*n+j] += value * b[k*n+j];
                }
            }
        }
#else
        for (int jj = 0; jj < n; jj += J_TILE) {
            const int je = jj + J_TILE < n ? jj + J_TILE : n;
            for (int j = jj; j < je; ++j) {
                double sum = 0.0;
#if SIMD && !defined(_MSC_VER)
                #pragma omp simd reduction(+:sum)
#endif
                for (int k = 0; k < n; ++k)
                    sum += a[i*n+k] * b[k*n+j];
                c[i*n+j] = sum;
            }
        }
#endif
    }
}

int main(int argc, char **argv) {
    if (argc < 2) return 2;
    const int n = atoi(argv[1]);
    const int seed = argc > 2 ? atoi(argv[2]) : 17;
    const int repeats = argc > 3 ? atoi(argv[3]) : 1;
    const int full = argc > 4 && strcmp(argv[4], "full") == 0;
    if (n < 1 || n > 2048 || repeats < 1 || repeats > 100 || seed < 0 || seed > 100000) return 2;
    const size_t bytes = (size_t)n * n * sizeof(double);
    double *a = (double *)malloc(bytes), *b = (double *)malloc(bytes), *c = (double *)malloc(bytes);
    if (!a || !b || !c) { free(a); free(b); free(c); return 3; }
    for (int i = 0; i < n; ++i)
        for (int j = 0; j < n; ++j) {
            a[i*n+j] = (double)((i*17 + j*3 + seed) % 13 - 6);
            b[i*n+j] = (double)((i*5 + j*11 + seed*2) % 17 - 8);
        }
    for (int repeat = 0; repeat < repeats; ++repeat) {
        memset(c, 0, bytes);
        multiply(a, b, c, n);
    }
    double checksum = 0;
    for (int i = 0; i < n*n; ++i) checksum += c[i] * (1 + i % 7);
    printf("{\"n\":%d,\"checksum\":%.0f", n, checksum);
    if (full) {
        printf(",\"matrix\":[");
        for (int i = 0; i < n*n; ++i) printf("%s%.0f", i ? "," : "", c[i]);
        printf("]");
    }
    printf("}\n");
    free(a); free(b); free(c);
    return 0;
}
