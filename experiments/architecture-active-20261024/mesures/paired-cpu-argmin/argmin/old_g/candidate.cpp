extern "C" void run(const void* input1, const void* input2, void* output,
                    int n, int parameter, int threads)
{
    const int* a = static_cast<const int*>(input1);
    int* result = static_cast<int*>(output);

    if (n <= 0) {
        *result = 0;
        return;
    }

    const int block_size = 512;
    int best_value = a[0];
    int best_block_base = 0;
    int best_block_end = 0;
    bool needs_index_recovery = false;

    for (int base = 0; base < n;) {
        const int remaining = n - base;
        const int count = remaining < block_size ? remaining : block_size;
        const int end = base + count;

        int block_min = a[base];
#pragma omp simd reduction(min:block_min)
        for (int i = base + 1; i < end; ++i) {
            if (a[i] < block_min) {
                block_min = a[i];
            }
        }

        if (block_min < best_value) {
            best_value = block_min;
            best_block_base = base;
            best_block_end = end;
            needs_index_recovery = true;
        }

        base = end;
    }

    int best_index = 0;
    if (needs_index_recovery) {
        best_index = best_block_base;
        while (best_index < best_block_end && a[best_index] != best_value) {
            ++best_index;
        }
    }

    *result = best_index;
}
