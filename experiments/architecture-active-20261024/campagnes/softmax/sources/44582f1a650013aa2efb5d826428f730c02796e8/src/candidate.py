import torch
import triton
import triton.language as tl


@triton.jit
def _streaming_softmax_row(X, Y, N: tl.constexpr, SX0: tl.constexpr, SX1: tl.constexpr, BLOCK: tl.constexpr):
    row = tl.program_id(0)
    offsets = tl.arange(0, BLOCK)
    acc_dtype = tl.float64 if X.dtype.element_ty == tl.float64 else tl.float32

    running_max = tl.full((), -float("inf"), acc_dtype)
    running_sum = tl.full((), 0.0, acc_dtype)

    # Accumulate the row's normalization statistics a tile at a time.
    for tile in range(tl.cdiv(N, BLOCK)):
        start = tile * BLOCK
        cols = start + offsets
        mask = cols < N
        values = tl.load(X + row * SX0 + cols * SX1, mask=mask, other=0).to(acc_dtype)
        values = tl.where(mask, values, -float("inf"))

        tile_max = tl.max(values, axis=0)
        tile_sum = tl.sum(tl.exp(values - tile_max), axis=0)
        new_max = tl.maximum(running_max, tile_max)
        running_sum = running_sum * tl.exp(running_max - new_max) + tile_sum * tl.exp(tile_max - new_max)
        running_max = new_max

    # Reread each tile to write normalized values without retaining the whole row.
    for tile in range(tl.cdiv(N, BLOCK)):
        start = tile * BLOCK
        cols = start + offsets
        mask = cols < N
        values = tl.load(X + row * SX0 + cols * SX1, mask=mask, other=0).to(acc_dtype)
        probs = tl.exp(values - running_max) / running_sum
        tl.store(Y + row * N + cols, probs, mask=mask)


def run(x):
    """Compute row-wise softmax with a tiled, online normalization pass."""
    rows, cols = x.shape
    y = torch.empty((rows, cols), device=x.device, dtype=x.dtype)
    if rows == 0:
        return y

    _streaming_softmax_row[(rows,)](
        x,
        y,
        cols,
        x.stride(0),
        x.stride(1),
        BLOCK=256,
        num_warps=4,
    )
    return y
