"""Generic, byte-preserving contracts for autonomous program experiments.

This module contains no benchmark algorithm or problem-specific input generator.
The operator freezes the execution contract; the untouched source is the oracle.
The file can also be copied into a campaign's protected directory and run standalone.
"""

from __future__ import annotations

import base64
import hashlib
import json
import math
import os
import shlex
import shutil
import struct
import subprocess
import sys
import tempfile
import time
from pathlib import Path, PurePosixPath

UNITS = {".c", ".cpp", ".cc", ".cxx"}
HEADERS = {".h", ".hpp", ".inc"}
FLAGS = {
    "-O0",
    "-O1",
    "-O2",
    "-O3",
    "-std=c99",
    "-std=c11",
    "-std=gnu99",
    "-std=gnu11",
    "-std=c++11",
    "-std=c++14",
    "-std=c++17",
    "-std=gnu++17",
    "-fopenmp",
    "-Werror=uninitialized",
    "-Werror=maybe-uninitialized",
    "-lm",
    "-pthread",
    "-lcrypto",
    "-DCOMPUTE_MD5_PROBLEM",
}
MAX_INPUT = 128 * 1024 * 1024
MAX_OUTPUT = 32 * 1024 * 1024


class ContractError(ValueError):
    def __init__(self, code, field, message, **details):
        self.diagnostic = {"code": code, "field": field, "message": message, **details}
        super().__init__(json.dumps(self.diagnostic, ensure_ascii=False))


def relative(name):
    if not isinstance(name, str) or not name or "\\" in name:
        raise ContractError("invalid_path", "path", "Expected a nonempty relative POSIX path")
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts or ":" in name or name in {".", ".."}:
        raise ContractError("invalid_path", "path", "Path leaves the experiment", value=name)
    return path.as_posix()


def sha(path):
    result = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def blob(raw):
    return {
        "base64": base64.b64encode(raw).decode("ascii"),
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }


def unblob(value):
    raw = base64.b64decode(value["base64"], validate=True)
    if len(raw) != value["bytes"] or hashlib.sha256(raw).hexdigest() != value["sha256"]:
        raise RuntimeError("Protected expected-output blob is inconsistent")
    return raw


def close_number(left, right, c):
    if left == right:
        return True
    return (
        math.isfinite(left)
        and math.isfinite(right)
        and math.isclose(left, right, abs_tol=c.get("abs_tol", 0), rel_tol=c.get("rel_tol", 0))
    )


def compare_bytes(expected, actual, c):
    mode = c.get("mode", "auto")
    if expected == actual:
        return True
    if mode == "bytes":
        return False
    if mode == "binary_numeric":
        record = struct.Struct(c["binary_format"])
        if len(actual) != len(expected) or not record.size or len(actual) % record.size:
            return False
        for left, right in zip(
            record.iter_unpack(expected), record.iter_unpack(actual), strict=True
        ):
            for x, y in zip(left, right, strict=True):
                if isinstance(x, float) and isinstance(y, float):
                    if not close_number(x, y, c):
                        return False
                elif x != y:
                    return False
        return True
    try:
        left, right = expected.decode("utf-8"), actual.decode("utf-8")
    except UnicodeDecodeError:
        return False  # auto handles binary by exact bytes; no decoding exception escapes.
    if mode == "auto" and ("\0" in left or "\0" in right):
        return False
    a, b = left.split(), right.split()
    if len(a) != len(b):
        return False
    for x, y in zip(a, b, strict=True):
        if x == y:
            continue
        try:
            if not close_number(float(x), float(y), c):
                return False
        except ValueError:
            return False
    return True


def equal_output(expected, actual, comparison):
    return expected.keys() == actual.keys() and all(
        compare_bytes(unblob(expected[key]), unblob(actual[key]), comparison) for key in expected
    )


def validate_contract(c, official, evidence_text=""):
    warnings = []
    available = sorted(
        p.relative_to(official).as_posix() for p in official.rglob("*") if p.is_file()
    )
    if c["language"] not in {"c", "c++"}:
        raise ContractError("language", "language", "Configured toolchain supports c and c++")
    units = []
    for name in c["source_files"]:
        name = relative(name)
        if name not in available:
            raise ContractError(
                "missing_unit",
                "source_files",
                "Source file does not exist",
                value=name,
                available_units=[p for p in available if Path(p).suffix in UNITS],
            )
        if Path(name).suffix.lower() in HEADERS:
            warnings.append(
                {
                    "code": "header_is_include",
                    "path": name,
                    "message": "Existing header copied unchanged; compiler include path supplies it",
                }
            )
        elif Path(name).suffix.lower() in UNITS:
            units.append(name)
        else:
            raise ContractError(
                "not_compilation_unit",
                "source_files",
                "File is neither a compilation unit nor a header",
                value=name,
            )
    if not units:
        raise ContractError("no_units", "source_files", "At least one translation unit is required")
    if any(flag not in FLAGS for flag in c["compiler_flags"]):
        raise ContractError(
            "compiler_option", "compiler_flags", "Option outside configured toolchain"
        )
    comparison = c["comparison"]
    if comparison.get("mode", "auto") not in {"auto", "text", "bytes", "binary_numeric"}:
        raise ContractError("comparison_mode", "comparison.mode", "Unknown output comparison mode")
    for key in ["abs_tol", "rel_tol"]:
        value = comparison.get(key, 0)
        if type(value) not in {int, float} or not math.isfinite(value) or not 0 <= value <= 1e-4:
            raise ContractError(
                "tolerance", "comparison." + key, "Tolerance must be finite in [0,1e-4]"
            )
    if comparison.get("abs_tol", 0) or comparison.get("rel_tol", 0):
        quote = " ".join(comparison.get("basis_quote", "").split())
        if len(quote) < 12 or quote not in " ".join(evidence_text.split()):
            raise ContractError(
                "unsupported_tolerance",
                "comparison.basis_quote",
                "Nonzero tolerance needs an exact quote from official material",
            )
    if comparison.get("mode") == "binary_numeric":
        fmt = comparison.get("binary_format", "")
        if (
            not fmt
            or fmt[0] not in "<>=!"
            or any(x not in "<>=!0123456789fdqQiIlLhHbB " for x in fmt)
        ):
            raise ContractError(
                "binary_format",
                "comparison.binary_format",
                "Expected an explicit-endian numeric struct format",
            )
        try:
            if not struct.Struct(fmt).size:
                raise struct.error("empty record")
        except struct.error as exc:
            raise ContractError("binary_format", "comparison.binary_format", str(exc)) from exc
    for phase in ["search_cases", "confirmation_cases"]:
        if not 1 <= len(c[phase]) <= 8:
            raise ContractError("case_count", phase, "One to eight cases are supported")
    for case in [*c["search_cases"], *c["confirmation_cases"], c["benchmark_case"]]:
        relative(case["name"])
        if len(case["argv"]) > 30 or any(not isinstance(a, str) or "\0" in a for a in case["argv"]):
            raise ContractError("arguments", case["name"] + ".argv", "Invalid data arguments")
        value = case["stdin"]
        if len(value) != 1 or next(iter(value)) not in {"official_file", "file", "text", "python"}:
            raise ContractError(
                "input_kind", case["name"] + ".stdin", "Choose exactly one input source"
            )
        file_value = value.get("file", value.get("official_file"))
        if file_value is not None and relative(file_value) not in available:
            raise ContractError(
                "missing_input",
                case["name"] + ".stdin",
                "Requested official input does not exist",
                value=file_value,
                available_files=available,
            )
        if sum(len(v) for v in value.values()) > 24000:
            raise ContractError(
                "input_specification_size",
                case["name"],
                "Input specification exceeds 24000 characters",
            )
        for entry in case.get("files", []):
            if relative(entry["source"]) not in available:
                raise ContractError(
                    "missing_asset",
                    case["name"] + ".files",
                    "Official data file does not exist",
                    value=entry["source"],
                )
            relative(entry["target"])
        for name in case.get("capture_files", []):
            relative(name)
    return list(dict.fromkeys(units)), warnings


def build_source(src, build, contract):
    build.mkdir(parents=True, exist_ok=True)
    compiler = shutil.which("g++" if contract["language"] == "c++" else "gcc")
    if not compiler:
        raise RuntimeError("Configured compiler is unavailable")
    command = [
        compiler,
        "-I",
        str(src),
        *[str(src / p) for p in contract["source_files"]],
        *contract["compiler_flags"],
        "-o",
        str(build / "solution"),
    ]
    result = subprocess.run(command, capture_output=True, timeout=90)
    (build / "compiler.stdout").write_bytes(result.stdout)
    (build / "compiler.stderr").write_bytes(result.stderr)
    if result.returncode:
        raise ContractError(
            "compilation_failed",
            "source_files/compiler_flags",
            "Compiler rejected the program",
            returncode=result.returncode,
            stderr=result.stderr.decode(errors="replace")[-12000:],
        )


def _generator_limits():
    import resource

    resource.setrlimit(resource.RLIMIT_FSIZE, (MAX_INPUT, MAX_INPUT))
    resource.setrlimit(resource.RLIMIT_CPU, (20, 20))


def materialize(case, official, root, resources):
    root.mkdir(parents=True, exist_ok=False)
    stdin = root / "stdin.data"
    value = case["stdin"]
    if "official_file" in value or "file" in value:
        shutil.copyfile(official / relative(value.get("file", value.get("official_file"))), stdin)
    elif "python" in value:
        generator = root / "fixture.py"
        generator.write_text(value["python"], encoding="utf-8")
        with stdin.open("wb") as stream:
            result = subprocess.run(
                [sys.executable, "-I", "-S", str(generator.resolve())],
                cwd=root,
                stdout=stream,
                stderr=subprocess.PIPE,
                timeout=20,
                preexec_fn=_generator_limits if os.name != "nt" else None,
            )
        if result.returncode:
            raise ContractError(
                "fixture_failed",
                case["name"],
                "Input fixture generator failed",
                stderr=result.stderr.decode(errors="replace")[-6000:],
            )
    else:
        stdin.write_text(value["text"], encoding="utf-8")
    if stdin.stat().st_size > MAX_INPUT:
        raise ContractError("input_size", case["name"], "Input exceeds 128 MiB")
    files = []
    fingerprint = hashlib.sha256(stdin.read_bytes())
    fingerprint.update(json.dumps(case["argv"]).encode())
    for entry in case.get("files", []):
        target = root / "assets" / relative(entry["target"])
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(official / relative(entry["source"]), target)
        fingerprint.update(entry["target"].encode())
        fingerprint.update(target.read_bytes())
        files.append(
            {"source": target.relative_to(resources).as_posix(), "target": entry["target"]}
        )
    return {
        "name": case["name"],
        "argv": case["argv"],
        "stdin": stdin.relative_to(resources).as_posix(),
        "stdin_bytes": stdin.stat().st_size,
        "input_fingerprint": fingerprint.hexdigest(),
        "files": files,
        "capture_files": case.get("capture_files", []),
    }


def execute(binary, case, timeout=60, resources=None):
    resources = resources or Path(__file__).parent
    started = time.perf_counter()
    with tempfile.TemporaryDirectory(prefix="forest-contract-") as tmp:
        cwd = Path(tmp)
        for entry in case["files"]:
            target = cwd / relative(entry["target"])
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(resources / entry["source"], target)
        captured = cwd / ".forest-stdout"
        with (resources / case["stdin"]).open("rb") as stream, captured.open("wb") as output:
            try:
                result = subprocess.run(
                    [str(Path(binary).resolve()), *case["argv"]],
                    cwd=cwd,
                    stdin=stream,
                    stdout=output,
                    stderr=subprocess.PIPE,
                    timeout=timeout,
                    env={
                        **os.environ,
                        "OMP_NUM_THREADS": "4",
                        "OMP_DYNAMIC": "FALSE",
                        "CUDA_VISIBLE_DEVICES": "",
                    },
                )
            except subprocess.TimeoutExpired as exc:
                raise ContractError(
                    "execution_timeout",
                    case["name"],
                    "Program exceeded its execution budget",
                    timeout_seconds=timeout,
                    input_bytes=case["stdin_bytes"],
                    input_fingerprint=case["input_fingerprint"],
                ) from exc
        if result.returncode:
            raise ContractError(
                "execution_failed",
                case["name"],
                "Program failed",
                returncode=result.returncode,
                stderr=result.stderr.decode(errors="replace")[-6000:],
            )
        outputs = {}
        for name, path in [
            ("stdout", captured),
            *[(n, cwd / relative(n)) for n in case["capture_files"]],
        ]:
            if not path.is_file() or path.stat().st_size > MAX_OUTPUT:
                raise ContractError(
                    "output_size_or_missing",
                    case["name"],
                    "Missing or oversized contracted output",
                    output=name,
                )
            outputs[name] = blob(path.read_bytes())
        return outputs, time.perf_counter() - started


def prepare(contract, official, root, *, evidence_text="", probe_timeout=60):
    units, warnings = validate_contract(contract, official, evidence_text)
    root = root.resolve()
    root.mkdir(parents=True, exist_ok=False)
    contract = json.loads(json.dumps(contract))
    contract["source_files"] = units
    source = root / "source"
    (source / "src").mkdir(parents=True)
    for p in official.rglob("*"):
        if p.is_file() and p.suffix.lower() in UNITS | HEADERS:
            target = source / "src" / p.relative_to(official)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(p, target)
    cc = "g++" if contract["language"] == "c++" else "gcc"
    cmd = [
        cc,
        "-I",
        "src",
        *["src/" + p for p in units],
        *contract["compiler_flags"],
        "-o",
        "solution",
    ]
    (source / "Makefile").write_text(
        "all: solution\nsolution: "
        + " ".join("src/" + p for p in units)
        + "\n\t"
        + shlex.join(cmd)
        + "\n",
        encoding="utf-8",
    )
    (source / "run.sh").write_text(
        '#!/bin/sh\ncd -- "$(dirname "$0")"\nexec ./solution "$@"\n', encoding="utf-8"
    )
    reference = root / "reference-build"
    build_source(source / "src", reference, contract)
    trusted = root / "validation"
    trusted.mkdir()
    shutil.copyfile(Path(__file__), trusted / "contract_tool.py")
    resolved = {
        key: contract[key] for key in ["language", "source_files", "compiler_flags", "comparison"]
    }
    cache, timings = {}, []
    for phase, cases in [
        ("search", contract["search_cases"]),
        ("confirmation", contract["confirmation_cases"]),
        ("benchmark", [contract["benchmark_case"]]),
    ]:
        seen, accepted = set(), []
        for index, case in enumerate(cases):
            actual = materialize(case, official, trusted / "fixtures" / phase / str(index), trusted)
            fp = actual["input_fingerprint"]
            key = (fp, tuple(actual["capture_files"]))
            if key in seen:
                warnings.append(
                    {
                        "code": "duplicate_case_collapsed",
                        "phase": phase,
                        "name": case["name"],
                        "input_fingerprint": fp,
                    }
                )
                continue
            seen.add(key)
            if key not in cache:
                expected, seconds = execute(reference / "solution", actual, probe_timeout, trusted)
                repeat, repeat_seconds = execute(
                    reference / "solution", actual, probe_timeout, trusted
                )
                if not any(item["bytes"] for item in expected.values()):
                    raise ContractError(
                        "empty_oracle", case["name"], "Reference produced no observable output"
                    )
                if not equal_output(expected, repeat, contract["comparison"]):
                    raise ContractError(
                        "unstable_oracle",
                        case["name"],
                        "Reference outputs do not agree under the proposed contract",
                    )
                wrong = {key: blob(b"WRONG_OUTPUT") for key in expected}
                if equal_output(expected, wrong, contract["comparison"]):
                    raise ContractError(
                        "negative_control", case["name"], "Comparator admitted the negative control"
                    )
                cache[key] = (expected, max(seconds, repeat_seconds))
                timings.append(
                    {
                        "name": case["name"],
                        "input_fingerprint": fp,
                        "seconds": [seconds, repeat_seconds],
                        "input_bytes": actual["stdin_bytes"],
                    }
                )
            actual["expected"], actual["reference_seconds"] = cache[key]
            accepted.append(actual)
        resolved[phase] = accepted if phase != "benchmark" else accepted[0]
    shared = sorted(
        {c["input_fingerprint"] for c in resolved["search"]}
        & {c["input_fingerprint"] for c in resolved["confirmation"]}
    )
    resolved["coverage"] = {
        "shared_search_confirmation_inputs": shared,
        "independent_input_sets": not shared,
    }
    slowest = max(seconds for _, seconds in cache.values())
    resolved["case_timeout_seconds"] = min(300, max(15, slowest * 4 + 5))
    write_json(trusted / "contract.json", resolved)
    write_json(root / "execution-contract.json", contract)
    bench = resolved["benchmark"]
    script = [
        "#!/bin/sh",
        "set -eu",
        'binary="$1"',
        'resources="$(CDPATH= cd -- "$(dirname "$0")" && pwd)"',
        'cd "$(dirname "$binary")"',
    ]
    for entry in bench["files"]:
        script.extend(
            [
                "mkdir -p " + shlex.quote(str(PurePosixPath(entry["target"]).parent)),
                'cp -- "$resources/"'
                + shlex.quote(entry["source"])
                + " "
                + shlex.quote(entry["target"]),
            ]
        )
    script.append(
        'exec "$binary" '
        + shlex.join(bench["argv"])
        + ' < "$resources/"'
        + shlex.quote(bench["stdin"])
    )
    (trusted / "benchmark.sh").write_text("\n".join(script) + "\n", encoding="utf-8")
    checker_seconds = max(
        sum(c["reference_seconds"] for c in resolved[p]) + bench["reference_seconds"]
        for p in ["search", "confirmation"]
    )
    receipt = {
        "ready": True,
        "source": str(source),
        "validation": str(trusted),
        "warnings": warnings,
        "reference_binary_sha256": sha(reference / "solution"),
        "reference_timings": timings,
        "coverage": resolved["coverage"],
        "benchmark_reference_seconds": bench["reference_seconds"],
        "protocol_timeout_seconds": min(1800, max(30, checker_seconds * 5 + 15)),
        "search_cases": len(resolved["search"]),
        "confirmation_cases": len(resolved["confirmation"]),
    }
    write_json(root / "preparation-receipt.json", receipt)
    return receipt


def main():
    root = Path(__file__).parent
    contract = json.loads((root / "contract.json").read_text(encoding="utf-8"))
    if sys.argv[1] == "build":
        build_source(Path(sys.argv[2]) / "src", Path(sys.argv[3]), contract)
    elif sys.argv[1] == "check":
        seen = set()
        count = 0
        for case in [*contract[sys.argv[3]], contract["benchmark"]]:
            key = (case["input_fingerprint"], tuple(case["capture_files"]))
            if key in seen:
                continue
            seen.add(key)
            actual, _ = execute(Path(sys.argv[2]), case, contract["case_timeout_seconds"], root)
            if not equal_output(case["expected"], actual, contract["comparison"]):
                print(
                    json.dumps(
                        {
                            "correct": False,
                            "case": case["name"],
                            "reason": "Reference output mismatch",
                        }
                    )
                )
                return 1
            count += 1
        print(json.dumps({"correct": True, "cases": count}))
    else:
        raise RuntimeError("Unknown contract operation")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ContractError as exc:
        print(json.dumps({"correct": False, "diagnostic": exc.diagnostic}), file=sys.stderr)
        raise SystemExit(1) from None
    except (OSError, RuntimeError, KeyError) as exc:
        print(
            json.dumps({"infrastructure_error": type(exc).__name__ + ": " + str(exc)}),
            file=sys.stderr,
        )
        raise SystemExit(70) from None
