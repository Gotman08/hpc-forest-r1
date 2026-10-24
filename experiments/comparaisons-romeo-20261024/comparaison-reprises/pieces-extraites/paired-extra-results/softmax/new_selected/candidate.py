import torch
import triton
import triton.language as tl


@triton.jit
def _online_softmax(
    X,
    Y,
    N: tl.constexpr,
    SX0: tl.constexpr,
    SX1: tl.constexpr,
    SY0: tl.constexpr,
    SY1: tl.constexpr,
    BLOCK: tl.constexpr,
):
    row = tl.program_id(0)
    offsets = tl.arange(0, BLOCK)
    running_max = tl.full((), -float("inf"), tl.float32)
    running_sum = tl.full((), 0.0, tl.float32)

    for chunk_idx in range(tl.cdiv(N, BLOCK)):
        cols = chunk_idx * BLOCK + offsets
        vals = tl.load(
            X + row * SX0 + cols * SX1,
            mask=cols < N,
            other=-float("inf"),
        ).to(tl.float32)
        chunk_max = tl.max(vals, axis=0)
        new_max = tl.maximum(running_max, chunk_max)
        chunk_sum = tl.sum(tl.exp(vals - new_max), axis=0)
        running_sum = running_sum * tl.exp(running_max - new_max) + chunk_sum
        running_max = new_max

    inv_sum = 1.0 / running_sum
    for chunk_idx in range(tl.cdiv(N, BLOCK)):
        cols = chunk_idx * BLOCK + offsets
        vals = tl.load(
            X + row * SX0 + cols * SX1,
            mask=cols < N,
            other=-float("inf"),
        ).to(tl.float32)
        probs = tl.exp(vals - running_max) * inv_sum
        tl.store(Y + row * SY0 + cols * SY1, probs, mask=cols < N)


def run(x):
    """Compute row-wise softmax with bounded, stable online reductions."""
    if x.ndim != 2:
        raise ValueError("run expects a 2D tensor")

    rows, cols = x.shape
    out = torch.empty_like(x)
    if rows == 0:
        return out
    if cols == 0:
        raise ValueError("softmax requires a non-empty reduction dimension")

    block = min(4096, triton.next_power_of_2(cols))
    num_warps = 2
    _online_softmax[(rows,)](
        x,
        out,
        cols,
        x.stride(0),
        x.stride(1),
        out.stride(0),
        out.stride(1),
        BLOCK=block,
        num_warps=num_warps,
    )
    return out
