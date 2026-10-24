#include <algorithm>
#include <cstddef>

#define UPDATE_ROW(a, c0, c1, c2, c3, c4, c5, c6, c7) \
    do { \
        c0 += (a) * b0; \
        c1 += (a) * b1; \
        c2 += (a) * b2; \
        c3 += (a) * b3; \
        c4 += (a) * b4; \
        c5 += (a) * b5; \
        c6 += (a) * b6; \
        c7 += (a) * b7; \
    } while (0)

extern "C" void run(const void* input1, const void* input2, void* output,
                    int n, int parameter, int threads) {
    (void)parameter;
    if (n <= 0) {
        return;
    }

    const float* A = static_cast<const float*>(input1);
    const float* B = static_cast<const float*>(input2);
    float* C = static_cast<float*>(output);
    const std::size_t nn = static_cast<std::size_t>(n);

    constexpr int kRowBlock = 32;
    constexpr int kColBlock = 64;
    const int row_tiles = (n - 1) / kRowBlock + 1;
    const int col_tiles = (n - 1) / kColBlock + 1;
    const long long tile_count = static_cast<long long>(row_tiles) * col_tiles;

    int workers = threads > 0 ? threads : 1;
    if (static_cast<long long>(workers) > tile_count) {
        workers = static_cast<int>(tile_count);
    }

#ifdef _OPENMP
#pragma omp parallel for schedule(static) num_threads(workers)
#endif
    for (long long tile = 0; tile < tile_count; ++tile) {
        const int rb = static_cast<int>(tile / col_tiles) * kRowBlock;
        const int cb = static_cast<int>(tile % col_tiles) * kColBlock;
        const int re = rb + std::min(kRowBlock, n - rb);
        const int ce = cb + std::min(kColBlock, n - cb);

        for (int r = rb; r < re; r += 4) {
            for (int c = cb; c < ce; c += 8) {
                if (re - r >= 4 && ce - c >= 8) {
                    float x00 = 0.0f, x01 = 0.0f, x02 = 0.0f, x03 = 0.0f;
                    float x04 = 0.0f, x05 = 0.0f, x06 = 0.0f, x07 = 0.0f;
                    float x10 = 0.0f, x11 = 0.0f, x12 = 0.0f, x13 = 0.0f;
                    float x14 = 0.0f, x15 = 0.0f, x16 = 0.0f, x17 = 0.0f;
                    float x20 = 0.0f, x21 = 0.0f, x22 = 0.0f, x23 = 0.0f;
                    float x24 = 0.0f, x25 = 0.0f, x26 = 0.0f, x27 = 0.0f;
                    float x30 = 0.0f, x31 = 0.0f, x32 = 0.0f, x33 = 0.0f;
                    float x34 = 0.0f, x35 = 0.0f, x36 = 0.0f, x37 = 0.0f;

                    const float* a0p = A + static_cast<std::size_t>(r) * nn;
                    const float* a1p = a0p + nn;
                    const float* a2p = a1p + nn;
                    const float* a3p = a2p + nn;
                    for (int k = 0; k < n; ++k) {
                        const float a0 = a0p[k];
                        const float a1 = a1p[k];
                        const float a2 = a2p[k];
                        const float a3 = a3p[k];
                        const float* bp = B + static_cast<std::size_t>(k) * nn + c;
                        const float b0 = bp[0];
                        const float b1 = bp[1];
                        const float b2 = bp[2];
                        const float b3 = bp[3];
                        const float b4 = bp[4];
                        const float b5 = bp[5];
                        const float b6 = bp[6];
                        const float b7 = bp[7];
                        UPDATE_ROW(a0, x00, x01, x02, x03, x04, x05, x06, x07);
                        UPDATE_ROW(a1, x10, x11, x12, x13, x14, x15, x16, x17);
                        UPDATE_ROW(a2, x20, x21, x22, x23, x24, x25, x26, x27);
                        UPDATE_ROW(a3, x30, x31, x32, x33, x34, x35, x36, x37);
                    }

                    float* out0 = C + static_cast<std::size_t>(r) * nn + c;
                    float* out1 = out0 + nn;
                    float* out2 = out1 + nn;
                    float* out3 = out2 + nn;
                    out0[0] = x00; out0[1] = x01; out0[2] = x02; out0[3] = x03;
                    out0[4] = x04; out0[5] = x05; out0[6] = x06; out0[7] = x07;
                    out1[0] = x10; out1[1] = x11; out1[2] = x12; out1[3] = x13;
                    out1[4] = x14; out1[5] = x15; out1[6] = x16; out1[7] = x17;
                    out2[0] = x20; out2[1] = x21; out2[2] = x22; out2[3] = x23;
                    out2[4] = x24; out2[5] = x25; out2[6] = x26; out2[7] = x27;
                    out3[0] = x30; out3[1] = x31; out3[2] = x32; out3[3] = x33;
                    out3[4] = x34; out3[5] = x35; out3[6] = x36; out3[7] = x37;
                } else {
                    const int r_end = r + std::min(4, re - r);
                    const int c_end = c + std::min(8, ce - c);
                    for (int i = r; i < r_end; ++i) {
                        for (int j = c; j < c_end; ++j) {
                            float sum = 0.0f;
                            const std::size_t a_base = static_cast<std::size_t>(i) * nn;
                            for (int k = 0; k < n; ++k) {
                                sum += A[a_base + static_cast<std::size_t>(k)] *
                                       B[static_cast<std::size_t>(k) * nn + j];
                            }
                            C[a_base + static_cast<std::size_t>(j)] = sum;
                        }
                    }
                }
            }
        }
    }
}

#undef UPDATE_ROW
