import torch
import triton
import triton.language as tl


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


def run(x):
    rows, cols = x.shape
    ret = torch.empty_like(x)
    acc_type = tl.float64 if x.dtype == torch.float64 else tl.float32
    _streaming_softmax_kernel[(rows,)](
        x,
        ret,
        cols,
        x.stride(0),
        x.stride(1),
        ret.stride(0),
        ret.stride(1),
        1024,
        acc_type,
        num_warps=4,
    )
    return ret
