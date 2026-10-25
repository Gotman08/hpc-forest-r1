#include <omp.h>

static int mandel(float c_re, float c_im, int count) {
    float z_re = c_re, z_im = c_im;
    int i;
    for (i = 0; i < count; ++i) {
        if (z_re * z_re + z_im * z_im > 4.f)
            break;

        float new_re = z_re * z_re - z_im * z_im;
        float new_im = 2.f * z_re * z_im;
        z_re = c_re + new_re;
        z_im = c_im + new_im;
    }

    return i;
}

void mandelbrot_serial(float x0, float y0, float x1, float y1, int width, int height, int maxIterations, int threads, int output[]) {
    float dx = (x1 - x0) / width;
    float dy = (y1 - y0) / height;

    const int tile_width = 64;
    const int tile_height = 16;
    const int tile_columns = width / tile_width + (width % tile_width != 0);
    const int tile_rows = height / tile_height + (height % tile_height != 0);
    const int worker_count = threads > 1 ? threads : 1;

    #pragma omp parallel for collapse(2) schedule(static) num_threads(worker_count) if(worker_count > 1)
    for (int tile_y_index = 0; tile_y_index < tile_rows; ++tile_y_index) {
        for (int tile_x_index = 0; tile_x_index < tile_columns; ++tile_x_index) {
            const int tile_y = tile_y_index * tile_height;
            const int tile_x = tile_x_index * tile_width;
            const int row_end = height - tile_y < tile_height ? height : tile_y + tile_height;
            const int column_end = width - tile_x < tile_width ? width : tile_x + tile_width;

            for (int j = tile_y; j < row_end; ++j) {
                for (int i = tile_x; i < column_end; ++i) {
                    float x = x0 + i * dx;
                    float y = y0 + j * dy;

                    int index = (j * width + i);
                    output[index] = mandel(x, y, maxIterations);
                }
            }
        }
    }
}

extern "C" void run(const void* input1, const void* input2, void* output, int n, int parameter, int threads) {
    const float* a = static_cast<const float*>(input1);
    mandelbrot_serial(a[0], a[1], a[2], a[3], n * 3 / 2, n, parameter, threads, static_cast<int*>(output));
}
