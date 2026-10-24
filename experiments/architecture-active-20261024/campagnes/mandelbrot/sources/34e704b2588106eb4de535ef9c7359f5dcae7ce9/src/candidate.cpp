static void mandelbrot_simd(float x0, float y0, float x1, float y1,
                            int width, int height, int maxIterations,
                            int threads, int output[]) {
    const float dx = (x1 - x0) / width;
    const float dy = (y1 - y0) / height;
    const int lane_count = 16;
    const int team_size = (threads > 1 && height > 1)
                              ? (threads < height ? threads : height)
                              : 1;

    #pragma omp parallel for schedule(static) num_threads(team_size) if (team_size > 1)
    for (int j = 0; j < height; ++j) {
        const float y = y0 + j * dy;

        for (int block = 0; block < width; ) {
            int valid = width - block;
            if (valid > lane_count)
                valid = lane_count;

            float c_re[16];
            float z_re[16];
            float z_im[16];
            int iterations[16];
            int active[16];

            #pragma omp simd
            for (int lane = 0; lane < lane_count; ++lane) {
                if (lane < valid) {
                    const int pixel = block + lane;
                    const float x = x0 + pixel * dx;
                    c_re[lane] = x;
                    z_re[lane] = x;
                    z_im[lane] = y;
                    iterations[lane] = 0;
                    active[lane] = 1;
                } else {
                    c_re[lane] = 0.0f;
                    z_re[lane] = 0.0f;
                    z_im[lane] = 0.0f;
                    iterations[lane] = 0;
                    active[lane] = 0;
                }
            }

            for (int iteration = 0; iteration < maxIterations; ++iteration) {
                int any_active = 0;
                #pragma omp simd reduction(|:any_active)
                for (int lane = 0; lane < lane_count; ++lane) {
                    if (active[lane]) {
                        if (z_re[lane] * z_re[lane] +
                            z_im[lane] * z_im[lane] > 4.0f) {
                            active[lane] = 0;
                        } else {
                            const float new_re = z_re[lane] * z_re[lane] -
                                                 z_im[lane] * z_im[lane];
                            const float new_im = 2.0f * z_re[lane] * z_im[lane];
                            z_re[lane] = c_re[lane] + new_re;
                            z_im[lane] = y + new_im;
                            ++iterations[lane];
                        }
                    }
                    any_active |= active[lane];
                }
                if (!any_active)
                    break;
            }

            #pragma omp simd
            for (int lane = 0; lane < valid; ++lane) {
                const int pixel = block + lane;
                output[j * width + pixel] = iterations[lane];
            }

            block += valid;
        }
    }
}

extern "C" void run(const void* input1, const void* input2, void* output,
                    int n, int parameter, int threads) {
    const float* a = static_cast<const float*>(input1);
    (void)input2;
    mandelbrot_simd(a[0], a[1], a[2], a[3], n * 3 / 2, n, parameter,
                    threads, static_cast<int*>(output));
}
