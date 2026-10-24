static void mandelbrot_simd(float x0, float y0, float x1, float y1,
                            int width, int height, int maxIterations,
                            int output[]) {
    constexpr int tile_size = 32;
    const float dx = (x1 - x0) / width;
    const float dy = (y1 - y0) / height;
    const int initial_result = maxIterations > 0 ? maxIterations : 0;

    for (int j = 0; j < height; ++j) {
        const float c_im = y0 + j * dy;
        int block_start = 0;

        while (block_start < width) {
            const int remaining = width - block_start;
            const int valid = remaining < tile_size ? remaining : tile_size;
            float c_re[tile_size];
            float z_re[tile_size];
            float z_im[tile_size];
            int result[tile_size];
            unsigned char active[tile_size];

            #pragma omp simd
            for (int lane = 0; lane < tile_size; ++lane) {
                result[lane] = initial_result;
                if (lane < valid) {
                    const int pixel = block_start + lane;
                    const float c_real = x0 + pixel * dx;
                    c_re[lane] = c_real;
                    z_re[lane] = c_real;
                    z_im[lane] = c_im;
                    active[lane] = maxIterations > 0 ? 1 : 0;
                } else {
                    c_re[lane] = 0.f;
                    z_re[lane] = 0.f;
                    z_im[lane] = 0.f;
                    active[lane] = 0;
                }
            }

            for (int iteration = 0; iteration < maxIterations; ++iteration) {
                int any_active = 0;
                #pragma omp simd reduction(|:any_active)
                for (int lane = 0; lane < tile_size; ++lane) {
                    if (active[lane]) {
                        const float current_re = z_re[lane];
                        const float current_im = z_im[lane];
                        if (current_re * current_re + current_im * current_im > 4.f) {
                            result[lane] = iteration;
                            active[lane] = 0;
                        } else {
                            const float new_re = current_re * current_re - current_im * current_im;
                            const float new_im = 2.f * current_re * current_im;
                            z_re[lane] = c_re[lane] + new_re;
                            z_im[lane] = c_im + new_im;
                            any_active = 1;
                        }
                    }
                }
                if (any_active == 0)
                    break;
            }

            #pragma omp simd
            for (int lane = 0; lane < valid; ++lane)
                output[j * width + block_start + lane] = result[lane];

            block_start += valid;
        }
    }
}

extern "C" void run(const void* input1, const void* input2, void* output,
                     int n, int parameter, int threads) {
    const float* a = static_cast<const float*>(input1);
    mandelbrot_simd(a[0], a[1], a[2], a[3], n * 3 / 2, n, parameter,
                    static_cast<int*>(output));
}
