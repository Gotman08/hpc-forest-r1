extern "C" void run(const void* input1, const void* input2, void* output, int n, int parameter, int threads)
{
    const int* a = static_cast<const int*>(input1);
    int best_index = 0;

    if (n < 8) {
        for (int i = 1; i < n; ++i) {
            if (a[i] < a[best_index]) best_index = i;
        }
        *static_cast<int*>(output) = best_index;
        return;
    }

    int min0 = a[0], idx0 = 0;
    int min1 = a[1], idx1 = 1;
    int min2 = a[2], idx2 = 2;
    int min3 = a[3], idx3 = 3;
    int min4 = a[4], idx4 = 4;
    int min5 = a[5], idx5 = 5;
    int min6 = a[6], idx6 = 6;
    int min7 = a[7], idx7 = 7;

    int i = 8;
    for (; i <= n - 8; i += 8) {
        int value = a[i];
        if (value < min0) { min0 = value; idx0 = i; }
        value = a[i + 1];
        if (value < min1) { min1 = value; idx1 = i + 1; }
        value = a[i + 2];
        if (value < min2) { min2 = value; idx2 = i + 2; }
        value = a[i + 3];
        if (value < min3) { min3 = value; idx3 = i + 3; }
        value = a[i + 4];
        if (value < min4) { min4 = value; idx4 = i + 4; }
        value = a[i + 5];
        if (value < min5) { min5 = value; idx5 = i + 5; }
        value = a[i + 6];
        if (value < min6) { min6 = value; idx6 = i + 6; }
        value = a[i + 7];
        if (value < min7) { min7 = value; idx7 = i + 7; }
    }

    int best = min0;
    best_index = idx0;
    if (min1 < best || (min1 == best && idx1 < best_index)) { best = min1; best_index = idx1; }
    if (min2 < best || (min2 == best && idx2 < best_index)) { best = min2; best_index = idx2; }
    if (min3 < best || (min3 == best && idx3 < best_index)) { best = min3; best_index = idx3; }
    if (min4 < best || (min4 == best && idx4 < best_index)) { best = min4; best_index = idx4; }
    if (min5 < best || (min5 == best && idx5 < best_index)) { best = min5; best_index = idx5; }
    if (min6 < best || (min6 == best && idx6 < best_index)) { best = min6; best_index = idx6; }
    if (min7 < best || (min7 == best && idx7 < best_index)) { best = min7; best_index = idx7; }

    for (; i < n; ++i) {
        if (a[i] < best) { best = a[i]; best_index = i; }
    }

    *static_cast<int*>(output) = best_index;
}
