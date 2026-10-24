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
def _streaming_softmax_kernel(
    X,
    Y,
    N: tl.constexpr,
    SX0: tl.constexpr,
    SX1: tl.constexpr,
    SY0: tl.constexpr,
    SY1: tl.constexpr,
    BLOCK: tl.constexpr,
    ACC_TYPE: tl.constexpr,
):
    row = tl.program_id(0)
    cols = tl.arange(0, BLOCK)
    running_max = tl.full((), -float("inf"), ACC_TYPE)
    running_sum = tl.full((), 0.0, ACC_TYPE)

    for base in range(0, N, BLOCK):
        offsets = base + cols
        mask = offsets < N
        values = tl.load(
            X + row * SX0 + offsets * SX1,
            mask=mask,
            other=-float("inf"),
        ).to(ACC_TYPE)
        tile_max = tl.max(values, axis=0)
        new_max = tl.maximum(running_max, tile_max)
        tile_sum = tl.sum(tl.exp(values - new_max), axis=0)
        running_sum = running_sum * tl.exp(running_max - new_max) + tile_sum
        running_max = new_max

    for base in range(0, N, BLOCK):
        offsets = base + cols
        mask = offsets < N
        values = tl.load(
            X + row * SX0 + offsets * SX1,
            mask=mask,
            other=-float("inf"),
        ).to(ACC_TYPE)
        output = tl.exp(values - running_max) / running_sum
        tl.store(Y + row * SY0 + offsets * SY1, output, mask=mask)


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
    result = torch.empty_like(x)
    is_fp64 = x.dtype == torch.float64

    # Use bounded live state for very wide rows; retain the measured direct
    # mapping for moderate widths, including the official performance width.
    if block_size >= 8192:
        acc_type = tl.float64 if is_fp64 else tl.float32
        stream_block = 1024 if width <= 1024 else 2048
        num_warps = 4 if width <= 1024 else 8
        _streaming_softmax_kernel[(rows,)](
            x,
            result,
            width,
            x.stride(0),
            x.stride(1),
            result.stride(0),
            result.stride(1),
            stream_block,
            acc_type,
            num_warps=num_warps,
        )
    else:
        num_warps = 2 if block_size >= 4096 else 4
        _row_softmax_kernel[(rows,)](
            x,
            result,
            x.stride(0),
            x.stride(1),
            result.stride(0),
            result.stride(1),
            width,
            block_size,
            is_fp64,
            num_warps=num_warps,
        )

    return result
