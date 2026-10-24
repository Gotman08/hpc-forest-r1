import torch
import triton
import triton.language as tl


@triton.jit
def _grouped_softmax_kernel(
    X,
    Y,
    M,
    N,
    stride_xm,
    stride_xn,
    stride_ym,
    stride_yn,
    ROWS_PER_CTA: tl.constexpr,
    BLOCK_N: tl.constexpr,
):
    rows = tl.program_id(0) * ROWS_PER_CTA + tl.arange(0, ROWS_PER_CTA)
    cols = tl.arange(0, BLOCK_N)
    row_mask = rows < M
    mask = row_mask[:, None] & (cols[None, :] < N)

    values = tl.load(
        X + rows[:, None] * stride_xm + cols[None, :] * stride_xn,
        mask=mask,
        other=-float("inf"),
    )
    if X.dtype.element_ty == tl.float64:
        values = values.to(tl.float64)
    else:
        values = values.to(tl.float32)

    row_max = tl.max(values, axis=1)
    row_max = tl.where(row_mask, row_max, 0.0)
    numerators = tl.exp(values - row_max[:, None])
    denominators = tl.sum(numerators, axis=1)
    denominators = tl.where(row_mask, denominators, 1.0)
    result = numerators / denominators[:, None]

    tl.store(
        Y + rows[:, None] * stride_ym + cols[None, :] * stride_yn,
        result,
        mask=mask,
    )


def run(x):
    m, n = x.shape
    ret = torch.empty_like(x)
    if m == 0:
        return ret

    block_n = triton.next_power_of_2(n)
    if block_n <= 128:
        rows_per_cta = 16
    elif block_n <= 512:
        rows_per_cta = 8
    elif block_n <= 2048:
        rows_per_cta = 4
    else:
        rows_per_cta = 2
    num_warps = 4 if block_n <= 1024 else 8

    _grouped_softmax_kernel[(triton.cdiv(m, rows_per_cta),)](
        x,
        ret,
        m,
        n,
        x.stride(0),
        x.stride(1),
        ret.stride(0),
        ret.stride(1),
        ROWS_PER_CTA=rows_per_cta,
        BLOCK_N=block_n,
        num_warps=num_warps,
    )
    return ret
