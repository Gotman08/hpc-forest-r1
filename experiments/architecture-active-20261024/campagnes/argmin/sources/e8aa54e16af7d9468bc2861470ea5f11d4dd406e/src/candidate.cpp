extern "C" void run(const void* input1, const void* input2, void* output, int n, int parameter, int threads)
{
    const int* a = static_cast<const int*>(input1);
    int j = 0;

    if (n >= 6) {
        int min0 = a[0], idx0 = 0;
        int min1 = a[1], idx1 = 1;
        int min2 = a[2], idx2 = 2;
        int min3 = a[3], idx3 = 3;
        int min4 = a[4], idx4 = 4;
        int min5 = a[5], idx5 = 5;
        int i = 6;

        for (; n - i >= 6; i += 6) {
            if (a[i] < min0) {
                min0 = a[i];
                idx0 = i;
            }
            if (a[i + 1] < min1) {
                min1 = a[i + 1];
                idx1 = i + 1;
            }
            if (a[i + 2] < min2) {
                min2 = a[i + 2];
                idx2 = i + 2;
            }
            if (a[i + 3] < min3) {
                min3 = a[i + 3];
                idx3 = i + 3;
            }
            if (a[i + 4] < min4) {
                min4 = a[i + 4];
                idx4 = i + 4;
            }
            if (a[i + 5] < min5) {
                min5 = a[i + 5];
                idx5 = i + 5;
            }
        }

        int best_value = min0;
        j = idx0;
        if (min1 < best_value || (min1 == best_value && idx1 < j)) {
            best_value = min1;
            j = idx1;
        }
        if (min2 < best_value || (min2 == best_value && idx2 < j)) {
            best_value = min2;
            j = idx2;
        }
        if (min3 < best_value || (min3 == best_value && idx3 < j)) {
            best_value = min3;
            j = idx3;
        }
        if (min4 < best_value || (min4 == best_value && idx4 < j)) {
            best_value = min4;
            j = idx4;
        }
        if (min5 < best_value || (min5 == best_value && idx5 < j)) {
            best_value = min5;
            j = idx5;
        }

        for (; i < n; ++i) {
            if (a[i] < best_value) {
                best_value = a[i];
                j = i;
            }
        }
    } else {
        for (int i = 1; i < n; ++i) {
            if (a[i] < a[j]) {
                j = i;
            }
        }
    }

    *static_cast<int*>(output) = j;
}
