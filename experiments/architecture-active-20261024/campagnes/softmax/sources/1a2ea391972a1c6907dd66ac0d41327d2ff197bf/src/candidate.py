import torch
import triton
import triton.language as tl


@triton.jit
def _softmax_grouped_rows(
    X,
    Y,
    M: tl.constexpr,
    N: tl.constexpr,
    X_STRIDE_M: tl.constexpr,
    X_STRIDE_N: tl.constexpr,
    Y_STRIDE_M: tl.constexpr,
    Y_STRIDE_N: tl.constexpr,
    BLOCK_N: tl.constexpr,
    ROWS: tl.constexpr,
):
    row_ids = tl.program_id(0) * ROWS + tl.arange(0, ROWS)
    col_ids = tl.arange(0, BLOCK_N)
    mask = (row_ids[:, None] < M) & (col_ids[None, :] < N)

    values = tl.load(
        X + row_ids[:, None] * X_STRIDE_M + col_ids[None, :] * X_STRIDE_N,
        mask=mask,
        other=-float("inf"),
    ).to(tl.float32)
    row_max = tl.max(values, axis=1)
    numerators = tl.exp(values - row_max[:, None])
    denominators = tl.sum(numerators, axis=1)
    probabilities = numerators / denominators[:, None]

    tl.store(
        Y + row_ids[:, None] * Y_STRIDE_M + col_ids[None, :] * Y_STRIDE_N,
        probabilities,
        mask=mask,
    )


def run(x):
    m, n = x.shape
    out = torch.empty_like(x)

    # Keep the reference operation's behavior for an empty reduction dimension.
    if n == 0:
        return x.max(dim=1)[0]
    if m == 0:
        return out

    block_n = triton.next_power_of_2(n)
    if block_n <= 128:
        rows_per_cta = 8
    elif block_n <= 1024:
        rows_per_cta = 4
    else:
        rows_per_cta = 2

    if block_n <= 1024:
        num_warps = 4
    else:
        num_warps = 8

    _softmax_grouped_rows[(triton.cdiv(m, rows_per_cta),)](
        x,
        out,
        m,
        n,
        x.stride(0),
        x.stride(1),
        out.stride(0),
        out.stride(1),
        BLOCK_N=block_n,
        ROWS=rows_per_cta,
        num_warps=num_warps,
    )
    return out
