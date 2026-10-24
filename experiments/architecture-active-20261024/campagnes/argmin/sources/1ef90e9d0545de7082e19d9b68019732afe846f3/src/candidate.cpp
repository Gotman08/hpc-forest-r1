#include <cstdint>
#include <cstring>
#include <cmath>
#include <algorithm>
#include <omp.h>

extern "C" void run(const void* input1, const void* input2, void* output,
                    int n, int parameter, int threads)
{
    const int* a = static_cast<const int*>(input1);
    int* result = static_cast<int*>(output);

    if (n <= 0) {
        *result = 0;
        return;
    }

    if (n < 4) {
        int best_index = 0;
        for (int i = 1; i < n; ++i) {
            if (a[i] < a[best_index]) {
                best_index = i;
            }
        }
        *result = best_index;
        return;
    }

    int min0 = a[0];
    int min1 = a[1];
    int min2 = a[2];
    int min3 = a[3];
    int index0 = 0;
    int index1 = 1;
    int index2 = 2;
    int index3 = 3;

    int i = 4;
    for (; i <= n - 4; i += 4) {
        const int x0 = a[i];
        const int x1 = a[i + 1];
        const int x2 = a[i + 2];
        const int x3 = a[i + 3];

        // Each lane visits increasing indices, so strict updates retain its earliest tie.
        if (x0 < min0) {
            min0 = x0;
            index0 = i;
        }
        if (x1 < min1) {
            min1 = x1;
            index1 = i + 1;
        }
        if (x2 < min2) {
            min2 = x2;
            index2 = i + 2;
        }
        if (x3 < min3) {
            min3 = x3;
            index3 = i + 3;
        }
    }

    int best_value = min0;
    int best_index = index0;
    if (min1 < best_value || (min1 == best_value && index1 < best_index)) {
        best_value = min1;
        best_index = index1;
    }
    if (min2 < best_value || (min2 == best_value && index2 < best_index)) {
        best_value = min2;
        best_index = index2;
    }
    if (min3 < best_value || (min3 == best_value && index3 < best_index)) {
        best_value = min3;
        best_index = index3;
    }

    for (; i < n; ++i) {
        if (a[i] < best_value || (a[i] == best_value && i < best_index)) {
            best_value = a[i];
            best_index = i;
        }
    }

    *result = best_index;
}
