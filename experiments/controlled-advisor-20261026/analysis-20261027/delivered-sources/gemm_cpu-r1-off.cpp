#include <algorithm>
#include <cstddef>
#include <omp.h>

static const int kRowsPerBand = 4;

static void multiply_four_rows(const float* A, const float* B, float* C,
                               int n, int r) {
    const std::size_t stride = static_cast<std::size_t>(n);

    int c = 0;
    for (; n - c >= 16; c += 16) {
        float s0[16] = {};
        float s1[16] = {};
        float s2[16] = {};
        float s3[16] = {};

        for (int k = 0; k < n; ++k) {
            const std::size_t kk = static_cast<std::size_t>(k);
            const float a0 = A[static_cast<std::size_t>(r) * stride + kk];
            const float a1 = A[static_cast<std::size_t>(r + 1) * stride + kk];
            const float a2 = A[static_cast<std::size_t>(r + 2) * stride + kk];
            const float a3 = A[static_cast<std::size_t>(r + 3) * stride + kk];
            const float* b = B + kk * stride + static_cast<std::size_t>(c);

            #pragma omp simd
            for (int j = 0; j < 16; ++j) {
                const float bv = b[j];
                s0[j] += a0 * bv;
                s1[j] += a1 * bv;
                s2[j] += a2 * bv;
                s3[j] += a3 * bv;
            }
        }

        float* out0 = C + static_cast<std::size_t>(r) * stride + static_cast<std::size_t>(c);
        float* out1 = C + static_cast<std::size_t>(r + 1) * stride + static_cast<std::size_t>(c);
        float* out2 = C + static_cast<std::size_t>(r + 2) * stride + static_cast<std::size_t>(c);
        float* out3 = C + static_cast<std::size_t>(r + 3) * stride + static_cast<std::size_t>(c);
        for (int j = 0; j < 16; ++j) {
            out0[j] = s0[j];
            out1[j] = s1[j];
            out2[j] = s2[j];
            out3[j] = s3[j];
        }
    }

    for (; c < n; ++c) {
        for (int rr = 0; rr < 4; ++rr) {
            const std::size_t row = static_cast<std::size_t>(r + rr);
            float sum = 0.0f;
            for (int k = 0; k < n; ++k) {
                const std::size_t kk = static_cast<std::size_t>(k);
                sum += A[row * stride + kk] * B[kk * stride + static_cast<std::size_t>(c)];
            }
            C[row * stride + static_cast<std::size_t>(c)] = sum;
        }
    }
}

static void multiply_partial_rows(const float* A, const float* B, float* C,
                                  int n, int first_row, int end_row) {
    const std::size_t stride = static_cast<std::size_t>(n);
    for (int r = first_row; r < end_row; ++r) {
        const std::size_t row = static_cast<std::size_t>(r);
        for (int c = 0; c < n; ++c) {
            float sum = 0.0f;
            for (int k = 0; k < n; ++k) {
                const std::size_t kk = static_cast<std::size_t>(k);
                sum += A[row * stride + kk] * B[kk * stride + static_cast<std::size_t>(c)];
            }
            C[row * stride + static_cast<std::size_t>(c)] = sum;
        }
    }
}

static void multiply_row_band(const float* A, const float* B, float* C,
                              int n, int first_row, int end_row) {
    if (end_row - first_row == kRowsPerBand) {
        multiply_four_rows(A, B, C, n, first_row);
    } else {
        multiply_partial_rows(A, B, C, n, first_row, end_row);
    }
}

extern "C" void run(const void* input1, const void* input2, void* output,
                    int n, int parameter, int threads) {
    (void)parameter;
    if (n <= 0) {
        return;
    }

    const float* A = static_cast<const float*>(input1);
    const float* B = static_cast<const float*>(input2);
    float* C = static_cast<float*>(output);

    const int band_count = n / kRowsPerBand + (n % kRowsPerBand != 0);
    const int requested_threads = threads > 0 ? threads : 1;
    const int team_size = std::min(requested_threads, band_count);

    if (team_size <= 1 || omp_in_parallel()) {
        for (int band = 0; band < band_count; ++band) {
            const int first_row = band * kRowsPerBand;
            const int remaining = n - first_row;
            const int end_row = first_row + (remaining < kRowsPerBand
                                                  ? remaining
                                                  : kRowsPerBand);
            multiply_row_band(A, B, C, n, first_row, end_row);
        }
        return;
    }

    const int previous_team_size = omp_get_max_threads();
    omp_set_num_threads(team_size);
    #pragma omp parallel for schedule(static)
    for (int band = 0; band < band_count; ++band) {
        const int first_row = band * kRowsPerBand;
        const int remaining = n - first_row;
        const int end_row = first_row + (remaining < kRowsPerBand
                                              ? remaining
                                              : kRowsPerBand);
        multiply_row_band(A, B, C, n, first_row, end_row);
    }
    omp_set_num_threads(previous_team_size);
}
