#include <cstddef>
#include <cstring>

namespace {
constexpr int kTileRows = 4;
constexpr int kTileCols = 128;
constexpr int kTileK = 16;

inline void multiply_tile(const float* a, const float* b, float* c, int n,
                          int row_begin, int col_begin) {
  const int row_end = (row_begin + kTileRows < n) ? row_begin + kTileRows : n;
  const int col_end = (col_begin + kTileCols < n) ? col_begin + kTileCols : n;
  const int col_count = col_end - col_begin;

  for (int kk = 0; kk < n; kk += kTileK) {
    const int k_end = (kk + kTileK < n) ? kk + kTileK : n;
    for (int i = row_begin; i < row_end; ++i) {
      const float* a_row = a + static_cast<std::size_t>(i) * n;
      float* c_row = c + static_cast<std::size_t>(i) * n + col_begin;
      for (int k = kk; k < k_end; ++k) {
        const float value = a_row[k];
        const float* b_row = b + static_cast<std::size_t>(k) * n + col_begin;
        for (int j = 0; j < col_count; ++j) {
          c_row[j] += value * b_row[j];
        }
      }
    }
  }
}
}  // namespace

extern "C" void run(const void* input1, const void* input2, void* output,
                    int n, int parameter, int threads) {
  (void)parameter;
  if (n <= 0) return;

  const std::size_t dimension = static_cast<std::size_t>(n);
  std::memset(output, 0, dimension * dimension * sizeof(float));

  int worker_count = threads;
  if (worker_count < 1) worker_count = 1;
  if (worker_count > 8) worker_count = 8;

  const float* a = static_cast<const float*>(input1);
  const float* b = static_cast<const float*>(input2);
  float* c = static_cast<float*>(output);

  if (n >= 256 && worker_count > 1) {
#pragma omp parallel for collapse(2) schedule(static) num_threads(worker_count)
    for (int row_begin = 0; row_begin < n; row_begin += kTileRows) {
      for (int col_begin = 0; col_begin < n; col_begin += kTileCols) {
        multiply_tile(a, b, c, n, row_begin, col_begin);
      }
    }
  } else {
    for (int row_begin = 0; row_begin < n; row_begin += kTileRows) {
      for (int col_begin = 0; col_begin < n; col_begin += kTileCols) {
        multiply_tile(a, b, c, n, row_begin, col_begin);
      }
    }
  }
}
