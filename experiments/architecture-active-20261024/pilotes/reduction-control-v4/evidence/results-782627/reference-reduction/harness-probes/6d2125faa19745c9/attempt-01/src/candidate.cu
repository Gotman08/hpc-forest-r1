#include <cuda_runtime.h>
#include <stddef.h>
#include <cub/block/block_reduce.cuh>

static const unsigned int BLOCK_SIZE = 128;
static const unsigned int TILE_ITEMS = 4096;
static const unsigned int FINALIZER_PARTIALS = 1024;

__device__ __forceinline__ long long reduce_block_128(long long value)
{
    typedef cub::BlockReduce<long long, BLOCK_SIZE,
                             cub::BLOCK_REDUCE_WARP_REDUCTIONS> BlockReduce;
    __shared__ typename BlockReduce::TempStorage temp_storage;
    return BlockReduce(temp_storage).Sum(value);
}

__global__ void write_zero(int *out)
{
    if (threadIdx.x == 0) {
        out[0] = 0;
    }
}

// Each CTA handles one bounded tile; each thread accumulates its strided
// elements in int64 before the CUB block reduction.
template <typename Input>
__global__ void reduce_tiles(const Input *input, long long *partials,
                             unsigned int count)
{
    const unsigned int tid = threadIdx.x;
    const unsigned int base = blockIdx.x * TILE_ITEMS;
    unsigned int end = base + TILE_ITEMS;
    if (end > count) {
        end = count;
    }

    long long value = 0;
    for (unsigned int i = base + tid; i < end; i += BLOCK_SIZE) {
        value += static_cast<long long>(input[i]);
    }

    const long long total = reduce_block_128(value);
    if (tid == 0) {
        partials[blockIdx.x] = total;
    }
}

// The direct path is bounded to one 4096-element tile, never the full large
// input. It uses the same 128-thread CUB reduction and writes the true total.
__global__ void reduce_input_direct(const int *input, int n, int *out)
{
    const unsigned int tid = threadIdx.x;
    long long value = 0;
    for (unsigned int i = tid; i < static_cast<unsigned int>(n);
         i += BLOCK_SIZE) {
        value += static_cast<long long>(input[i]);
    }

    const long long total = reduce_block_128(value);
    if (tid == 0) {
        out[0] = static_cast<int>(total);
    }
}

// The host launches this only when count is at most FINALIZER_PARTIALS.
__global__ void finalize_partials(const long long *partials,
                                  unsigned int count, int *out)
{
    const unsigned int tid = threadIdx.x;
    long long value = 0;
    for (unsigned int i = tid; i < count; i += BLOCK_SIZE) {
        value += partials[i];
    }

    const long long total = reduce_block_128(value);
    if (tid == 0) {
        out[0] = static_cast<int>(total);
    }
}

extern "C" void run(const void *x, const void *k, const void *gy,
                    void *out, void *scratch, int n, int h, int l, int ks)
{
    (void)k;
    (void)gy;
    (void)h;
    (void)l;
    (void)ks;

    if (out == NULL || n < 0) {
        return;
    }
    if (n == 0) {
        write_zero<<<1, 1>>>(static_cast<int *>(out));
        return;
    }
    if (x == NULL) {
        return;
    }

    if (static_cast<unsigned int>(n) <= TILE_ITEMS) {
        reduce_input_direct<<<1, BLOCK_SIZE>>>(
            static_cast<const int *>(x), n, static_cast<int *>(out));
        return;
    }
    if (scratch == NULL) {
        return;
    }

    const unsigned int input_count = static_cast<unsigned int>(n);
    unsigned int partial_count = (input_count + TILE_ITEMS - 1) / TILE_ITEMS;
    long long *partials0 = static_cast<long long *>(scratch);

    // Preserve the baseline scratch separation convention. Both partial
    // buffers are much smaller than the corresponding int-sized input range.
    const size_t second_offset =
        (static_cast<size_t>(n) + 32768u) * sizeof(int);
    long long *partials1 = reinterpret_cast<long long *>(
        static_cast<char *>(scratch) + second_offset);

    reduce_tiles<int><<<partial_count, BLOCK_SIZE>>>(
        static_cast<const int *>(x), partials0, input_count);

    long long *source = partials0;
    long long *destination = partials1;
    while (partial_count > FINALIZER_PARTIALS) {
        const unsigned int next_count =
            (partial_count + TILE_ITEMS - 1) / TILE_ITEMS;
        reduce_tiles<long long><<<next_count, BLOCK_SIZE>>>(
            source, destination, partial_count);
        partial_count = next_count;

        long long *tmp = source;
        source = destination;
        destination = tmp;
    }

    finalize_partials<<<1, BLOCK_SIZE>>>(source, partial_count,
                                          static_cast<int *>(out));
}
