import torch
import triton
import triton.language as tl


@triton.jit
def _row_softmax_kernel(
    X,
    Y,
    stride_xm: tl.constexpr,
    stride_xn: tl.constexpr,
    stride_ym: tl.constexpr,
    stride_yn: tl.constexpr,
    N: tl.constexpr,
    BLOCK_SIZE: tl.constexpr,
    IS_FP64: tl.constexpr,
):
    row = tl.program_id(0)
    cols = tl.arange(0, BLOCK_SIZE)
    mask = cols < N
    values = tl.load(
        X + row * stride_xm + cols * stride_xn,
        mask=mask,
        other=-float("inf"),
    )

    if IS_FP64:
        values = values.to(tl.float64)
    else:
        values = values.to(tl.float32)

    row_max = tl.max(values, axis=0)
    exp_values = tl.exp(values - row_max)
    denominator = tl.sum(exp_values, axis=0)
    result = exp_values / denominator
    tl.store(
        Y + row * stride_ym + cols * stride_yn,
        result,
        mask=mask,
    )


@triton.jit
def _grouped_softmax_kernel(
    X,
    Y,
    stride_xm: tl.constexpr,
    stride_xn: tl.constexpr,
    stride_ym: tl.constexpr,
    stride_yn: tl.constexpr,
    M: tl.constexpr,
    N: tl.constexpr,
    ROWS_PER_CTA: tl.constexpr,
    BLOCK_N: tl.constexpr,
    IS_FP64: tl.constexpr,
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
    if IS_FP64:
        values = values.to(tl.float64)
    else:
        values = values.to(tl.float32)

    row_max = tl.max(values, axis=1)
    row_max = tl.where(row_mask, row_max, 0.0)
    exp_values = tl.exp(values - row_max[:, None])
    denominator = tl.sum(exp_values, axis=1)
    denominator = tl.where(row_mask, denominator, 1.0)
    result = exp_values / denominator[:, None]

    tl.store(
        Y + rows[:, None] * stride_ym + cols[None, :] * stride_yn,
        result,
        mask=mask,
    )


def _torch_softmax(x):
    x_max = x.max(dim=1)[0]
    numerator = torch.exp(x - x_max[:, None])
    denominator = numerator.sum(dim=1)
    return numerator / denominator[:, None]


def run(x):
    if (
        x.device.type != "cuda"
        or x.ndim != 2
        or x.requires_grad
        or x.shape[0] == 0
        or x.shape[1] == 0
        or x.dtype not in (torch.float16, torch.bfloat16, torch.float32, torch.float64)
    ):
        return _torch_softmax(x)

    rows, width = x.shape
    block_size = triton.next_power_of_2(width)
    y = torch.empty_like(x)
    is_fp64 = x.dtype == torch.float64

    # Group narrow rows; retain one row per CTA for wider reductions.
    if block_size <= 2048:
        if block_size <= 128:
            rows_per_cta = 16
        elif block_size <= 512:
            rows_per_cta = 8
        else:
            rows_per_cta = 4
        num_warps = 4 if block_size <= 1024 else 8
        _grouped_softmax_kernel[(triton.cdiv(rows, rows_per_cta),)](
            x,
            y,
            x.stride(0),
            x.stride(1),
            y.stride(0),
            y.stride(1),
            rows,
            width,
            rows_per_cta,
            block_size,
            is_fp64,
            num_warps=num_warps,
        )
    else:
        num_warps = 2 if block_size >= 4096 else 4
        _row_softmax_kernel[(rows,)](
            x,
            y,
            x.stride(0),
            x.stride(1),
            y.stride(0),
            y.stride(1),
            width,
            block_size,
            is_fp64,
            num_warps=num_warps,
        )
    return y
