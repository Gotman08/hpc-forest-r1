#include <omp.h>
#include <vector>

static void mandelbrot_serial(float x0, float y0, float x1, float y1,
                              int width, int height, int maxIterations,
                              int output[]) {
    const float dx = (x1 - x0) / width;
    const float dy = (y1 - y0) / height;
    const int initial_result = maxIterations > 0 ? maxIterations : 0;

    std::vector<float> c_re(width);
    std::vector<float> z_re(width);
    std::vector<float> z_im(width);
    std::vector<int> result(width);
    std::vector<unsigned char> active(width);

    for (int j = 0; j < height; ++j) {
        const float c_im = y0 + j * dy;

        #pragma omp simd
        for (int i = 0; i < width; ++i) {
            const float c_real = x0 + i * dx;
            c_re[i] = c_real;
            z_re[i] = c_real;
            z_im[i] = c_im;
            result[i] = initial_result;
            active[i] = maxIterations > 0 ? 1 : 0;
        }

        for (int iteration = 0; iteration < maxIterations; ++iteration) {
            int any_active = 0;
            #pragma omp simd reduction(|:any_active)
            for (int i = 0; i < width; ++i) {
                if (active[i]) {
                    const float current_re = z_re[i];
                    const float current_im = z_im[i];
                    if (current_re * current_re + current_im * current_im > 4.f) {
                        result[i] = iteration;
                        active[i] = 0;
                    } else {
                        const float new_re = current_re * current_re - current_im * current_im;
                        const float new_im = 2.f * current_re * current_im;
                        z_re[i] = c_re[i] + new_re;
                        z_im[i] = c_im + new_im;
                        any_active = 1;
                    }
                }
            }
            if (any_active == 0)
                break;
        }

        #pragma omp simd
        for (int i = 0; i < width; ++i)
            output[j * width + i] = result[i];
    }
}

extern "C" void run(const void* input1, const void* input2, void* output,
                     int n, int parameter, int threads) {
    const float* a = static_cast<const float*>(input1);
    mandelbrot_serial(a[0], a[1], a[2], a[3], n * 3 / 2, n, parameter,
                      static_cast<int*>(output));
}
