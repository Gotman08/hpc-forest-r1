import torch
import triton
import triton.language as tl


@triton.jit
def _softmax_row_kernel(
    X,
    Y,
    N: tl.constexpr,
    X_ROW_STRIDE: tl.constexpr,
    X_COL_STRIDE: tl.constexpr,
    Y_ROW_STRIDE: tl.constexpr,
    Y_COL_STRIDE: tl.constexpr,
    BLOCK: tl.constexpr,
):
    row = tl.program_id(0)
    cols = tl.arange(0, BLOCK)
    mask = cols < N
    offsets = row * X_ROW_STRIDE + cols * X_COL_STRIDE
    values = tl.load(X + offsets, mask=mask, other=0)

    if X.dtype.element_ty == tl.float64:
        values = values.to(tl.float64)
    else:
        values = values.to(tl.float32)

    values = tl.where(mask, values, -float("inf"))
    row_max = tl.max(values, axis=0)
    exponentials = tl.exp(values - row_max)
    denominator = tl.sum(exponentials, axis=0)
    result = exponentials / denominator

    out_offsets = row * Y_ROW_STRIDE + cols * Y_COL_STRIDE
    tl.store(Y + out_offsets, result, mask=mask)


def _torch_softmax(x):
    x_max = x.max(dim=1)[0]
    z = x - x_max[:, None]
    numerator = torch.exp(z)
    denominator = numerator.sum(dim=1)
    return numerator / denominator[:, None]


def run(x):
    if (
        x.device.type != "cuda"
        or x.ndim != 2
        or not x.is_floating_point()
        or x.requires_grad
    ):
        return _torch_softmax(x)

    n_rows, n_cols = x.shape
    output = torch.empty_like(x)
    if n_rows == 0 or n_cols == 0:
        return output

    block = triton.next_power_of_2(n_cols)
    _softmax_row_kernel[(n_rows,)](
        x,
        output,
        n_cols,
        x.stride(0),
        x.stride(1),
        output.stride(0),
        output.stride(1),
        block,
        num_warps=4,
    )
    return output
