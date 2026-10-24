import torch
import triton
import triton.language as tl


@triton.jit
def _row_softmax_kernel(
    X,
    Y,
    N: tl.constexpr,
    X_STRIDE0: tl.constexpr,
    X_STRIDE1: tl.constexpr,
    Y_STRIDE0: tl.constexpr,
    Y_STRIDE1: tl.constexpr,
    BLOCK_SIZE: tl.constexpr,
):
    row_idx = tl.program_id(0)
    cols = tl.arange(0, BLOCK_SIZE)
    x_ptrs = X + row_idx * X_STRIDE0 + cols * X_STRIDE1
    raw = tl.load(x_ptrs, mask=cols < N, other=0)

    if X.dtype.element_ty == tl.float64:
        row = raw.to(tl.float64)
    else:
        row = raw.to(tl.float32)
    row = tl.where(cols < N, row, -float("inf"))

    row_max = tl.max(row, axis=0)
    numer = tl.exp(row - row_max)
    denom = tl.sum(numer, axis=0)
    result = numer / denom

    y_ptrs = Y + row_idx * Y_STRIDE0 + cols * Y_STRIDE1
    tl.store(y_ptrs, result, mask=cols < N)


def run(x):
    """Compute a stable row-wise softmax with one Triton program per row."""
    if not x.is_cuda:
        x_max = x.max(dim=1)[0]
        numerator = torch.exp(x - x_max[:, None])
        denominator = numerator.sum(dim=1)
        return numerator / denominator[:, None]

    rows, cols = x.shape
    out_dtype = x.dtype if x.is_floating_point() else torch.float32
    out = torch.empty_like(x, dtype=out_dtype)
    if rows == 0:
        return out

    block_size = triton.next_power_of_2(cols)
    if block_size <= 128:
        num_warps = 1
    elif block_size <= 2048:
        num_warps = 4
    else:
        num_warps = 8

    _row_softmax_kernel[(rows,)](
        x,
        out,
        cols,
        x.stride(0),
        x.stride(1),
        out.stride(0),
        out.stride(1),
        BLOCK_SIZE=block_size,
        num_warps=num_warps,
    )
    return out
