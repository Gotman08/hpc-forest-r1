extern "C" void run(const void* input1, const void* input2, void* output, int n, int parameter, int threads)
{
    const int* a = static_cast<const int*>(input1);
    int j = 0;

    if (n >= 2) {
        int min0 = a[0];
        int idx0 = 0;
        int min1 = a[1];
        int idx1 = 1;
        int i = 2;

        for (; i + 1 < n; i += 2) {
            if (a[i] < min0) {
                min0 = a[i];
                idx0 = i;
            }
            if (a[i + 1] < min1) {
                min1 = a[i + 1];
                idx1 = i + 1;
            }
        }

        j = idx0;
        if (min1 < min0 || (min1 == min0 && idx1 < idx0)) {
            j = idx1;
        }
        if (i < n && a[i] < a[j]) {
            j = i;
        }
    }

    *static_cast<int*>(output) = j;
}
