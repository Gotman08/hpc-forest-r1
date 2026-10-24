import torch
import triton
import triton.language as tl


@triton.jit
def _grouped_row_softmax(
    X,
    Y,
    M: tl.constexpr,
    N: tl.constexpr,
    BM: tl.constexpr,
    BN: tl.constexpr,
):
    row_ids = tl.program_id(0) * BM + tl.arange(0, BM)
    col_ids = tl.arange(0, BN)
    mask = (row_ids[:, None] < M) & (col_ids[None, :] < N)

    values = tl.load(
        X + row_ids[:, None] * N + col_ids[None, :],
        mask=mask,
        other=-float("inf"),
    )
    row_max = tl.max(values, axis=1)
    row_max = tl.where(row_ids < M, row_max, 0.0)
    numerators = tl.exp(values - row_max[:, None])
    denominators = tl.sum(numerators, axis=1)
    denominators = tl.where(row_ids < M, denominators, 1.0)
    result = numerators / denominators[:, None]

    tl.store(
        Y + row_ids[:, None] * N + col_ids[None, :],
        result,
        mask=mask,
    )


def run(x):
    rows, cols = x.shape
    output = torch.empty_like(x)
    if rows == 0 or cols == 0:
        return output

    block_n = triton.next_power_of_2(cols)
    if cols <= 128:
        block_m = 4
    elif cols <= 1024:
        block_m = 2
    else:
        block_m = 1

    _grouped_row_softmax[(triton.cdiv(rows, block_m),)](
        x,
        output,
        rows,
        cols,
        block_m,
        block_n,
        num_warps=4,
    )
    return output
