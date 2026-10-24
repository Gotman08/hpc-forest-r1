#include <cstddef>
#include <cuda_runtime.h>

__global__ void sgemm_register_blocked(int M, int N, int K, float alpha,
                                       const float *A, const float *B,
                                       float beta, float *C) {
  // Visit dense 2x2 CTA macro-groups in row-major order, including ragged edges.
  const size_t tile_cols = static_cast<size_t>(gridDim.x);
  const size_t tile_rows = static_cast<size_t>(gridDim.y);
  const size_t cta_id = static_cast<size_t>(blockIdx.y) * tile_cols +
                        static_cast<size_t>(blockIdx.x);

  const size_t full_row_bands = tile_rows / 2;
  const size_t full_band_size = 2 * tile_cols;
  const size_t full_band_ctas = full_row_bands * full_band_size;
  size_t band_y;
  size_t offset_in_band;
  size_t rows_in_band;
  if (cta_id < full_band_ctas) {
    band_y = cta_id / full_band_size;
    offset_in_band = cta_id % full_band_size;
    rows_in_band = 2;
  } else {
    band_y = full_row_bands;
    offset_in_band = cta_id - full_band_ctas;
    rows_in_band = 1;
  }

  const size_t full_col_groups = tile_cols / 2;
  const size_t ctas_per_full_col_group = 2 * rows_in_band;
  const size_t full_col_group_ctas = full_col_groups * ctas_per_full_col_group;
  size_t col_group;
  size_t local_offset;
  size_t cols_in_group;
  if (offset_in_band < full_col_group_ctas) {
    col_group = offset_in_band / ctas_per_full_col_group;
    local_offset = offset_in_band % ctas_per_full_col_group;
    cols_in_group = 2;
  } else {
    col_group = full_col_groups;
    local_offset = offset_in_band - full_col_group_ctas;
    cols_in_group = 1;
  }

  const size_t tile_y = band_y * 2 + local_offset / cols_in_group;
  const size_t tile_x = col_group * 2 + local_offset % cols_in_group;
  const size_t row0 = tile_y * 8 + threadIdx.y;
  const size_t row1 = row0 + 4;
  const size_t col0 = tile_x * 128 + threadIdx.x;
  const size_t col1 = col0 + 32;
  const size_t col2 = col0 + 64;
  const size_t col3 = col0 + 96;

  if (row0 >= static_cast<size_t>(N) || col0 >= static_cast<size_t>(M)) return;

  float acc00 = 0.0f;
  float acc01 = 0.0f;
  float acc02 = 0.0f;
  float acc03 = 0.0f;
  float acc10 = 0.0f;
  float acc11 = 0.0f;
  float acc12 = 0.0f;
  float acc13 = 0.0f;

  for (int p = 0; p < K; ++p) {
    const size_t a_col = static_cast<size_t>(p);
    const size_t b_row = static_cast<size_t>(p) * static_cast<size_t>(M);
    const float a0 = A[row0 * static_cast<size_t>(K) + a_col];
    const float a1 = row1 < static_cast<size_t>(N)
                         ? A[row1 * static_cast<size_t>(K) + a_col]
                         : 0.0f;
    const float b0 = B[b_row + col0];

    acc00 += a0 * b0;
    acc10 += a1 * b0;
    if (col1 < static_cast<size_t>(M)) {
      const float b1 = B[b_row + col1];
      acc01 += a0 * b1;
      acc11 += a1 * b1;
    }
    if (col2 < static_cast<size_t>(M)) {
      const float b2 = B[b_row + col2];
      acc02 += a0 * b2;
      acc12 += a1 * b2;
    }
    if (col3 < static_cast<size_t>(M)) {
      const float b3 = B[b_row + col3];
      acc03 += a0 * b3;
      acc13 += a1 * b3;
    }
  }

  const size_t c_row0 = row0 * static_cast<size_t>(M);
  C[c_row0 + col0] = alpha * acc00 + beta * C[c_row0 + col0];
  if (col1 < static_cast<size_t>(M))
    C[c_row0 + col1] = alpha * acc01 + beta * C[c_row0 + col1];
  if (col2 < static_cast<size_t>(M))
    C[c_row0 + col2] = alpha * acc02 + beta * C[c_row0 + col2];
  if (col3 < static_cast<size_t>(M))
    C[c_row0 + col3] = alpha * acc03 + beta * C[c_row0 + col3];

  if (row1 < static_cast<size_t>(N)) {
    const size_t c_row1 = row1 * static_cast<size_t>(M);
    C[c_row1 + col0] = alpha * acc10 + beta * C[c_row1 + col0];
    if (col1 < static_cast<size_t>(M))
      C[c_row1 + col1] = alpha * acc11 + beta * C[c_row1 + col1];
    if (col2 < static_cast<size_t>(M))
      C[c_row1 + col2] = alpha * acc12 + beta * C[c_row1 + col2];
    if (col3 < static_cast<size_t>(M))
      C[c_row1 + col3] = alpha * acc13 + beta * C[c_row1 + col3];
  }
}

extern "C" void run(const float *A, const float *B, float *C, float *scratch,
                    int n, int m, int k, float alpha, float beta) {
  if (n <= 0 || m <= 0) return;
  const int blocks_x = m / 128 + (m % 128 != 0);
  const int blocks_y = n / 8 + (n % 8 != 0);
  sgemm_register_blocked<<<dim3(blocks_x, blocks_y), dim3(32, 4)>>>(
      n, m, k, alpha, A, B, beta, C);
}
