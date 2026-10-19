"""Execution/data preparation only. No solution or optimization of a contest task."""

import shutil
import struct
import sys
from pathlib import Path

from hpc_forest import contracts as c


def subsample(values, count, offset=0):
    count = min(count, len(values))
    return [
        values[(i * len(values) // count + offset) % len(values)] for i in range(count)
    ]


def fixture_writer(slug, official, bundle):
    """Copy records, never calculate the answer to any problem."""
    if slug == "knn":
        datasets = []
        for name in ["large.in", "example.in"]:
            with (official / name).open(encoding="ascii") as f:
                n = int(f.readline().split("=")[1])
                groups = []
                for _ in range(n):
                    label = f.readline().strip()
                    length = int(f.readline().split("=")[1])
                    groups.append(
                        (label, [f.readline().strip() for _ in range(length)])
                    )
                k = int(f.readline().split("=")[1])
                query = f.readline().strip()
            datasets.append((groups, k, query))

        def write(count, name, holdout=False, parameter=None):
            groups, k, query = datasets[int(holdout)]
            sampled = [
                (label, subsample(points, count, int(holdout)))
                for label, points in groups
            ]
            original_total = sum(len(points) for _, points in groups)
            sampled_total = sum(len(points) for _, points in sampled)
            k = max(1, min(sampled_total, round(k * sampled_total / original_total)))
            rows = ["n_groups=" + str(len(sampled))]
            for label, points in sampled:
                rows.extend([label, "length=" + str(len(points)), *points])
            rows.extend(["k=" + str(k), query])
            path = bundle / "fixtures" / (name + ".in")
            path.write_text("\n".join(rows) + "\n", encoding="ascii")
            return path, {
                "points_per_group": count,
                "points_total": sum(len(p) for _, p in sampled),
                "k": k,
                "source": "example.in" if holdout else "large.in",
            }

        return (
            write,
            [128, 512, 2048, 8192, 32768],
            [(3, None), (17, None), (129, None)],
            [(7, None), (65, None), (257, None)],
        )
    if slug == "sum":
        with (official / "input").open(encoding="ascii") as f:
            n, s = map(int, f.readline().split())
            first, last = [], []
            cap = min(n, 1024)
            for row in range(n):
                values = f.readline().split()
                if row < cap:
                    first.append(values[:cap])
                if row >= n - cap:
                    last.append(values[-cap:])

        def write(count, name, holdout=False, parameter=None):
            count = min(count, cap)
            window = (
                max(1, min(count - 1, round(s * count / n)))
                if parameter is None
                else min(count - 1, parameter)
            )
            data = last if holdout else first
            rows = data[-count:] if holdout else data[:count]
            path = bundle / "fixtures" / (name + ".in")
            with path.open("w", encoding="ascii") as stream:
                stream.write(f"{count} {window}\n")
                for row in rows:
                    values = row[-count:] if holdout else row[:count]
                    stream.write(" ".join(values) + "\n")
            return path, {
                "matrix_size": count,
                "window_size": window,
                "source": "input",
                "region": "last" if holdout else "first",
            }

        return (
            write,
            [64, 128, 256, 512, 1024],
            [(23, None), (64, 1), (65, 64)],
            [(31, None), (97, 96), (128, 1)],
        )
    if slug == "nbody":
        if (
            sys.byteorder != "little"
            or struct.calcsize("i") != 4
            or struct.calcsize("f") != 4
        ):
            raise RuntimeError(
                "Official binary dataset requires this prepared little-endian 32-bit int/float ABI"
            )
        raw = (official / "input").read_bytes()
        count = struct.unpack("<i", raw[:4])[0]
        if len(raw) != 4 + count * 24:
            raise RuntimeError(
                "Official binary dataset size does not match its declared record count"
            )
        records = [raw[i : i + 24] for i in range(4, len(raw), 24)]

        def write(count, name, holdout=False, parameter=None):
            records_chosen = subsample(records, count, int(holdout))
            path = bundle / "fixtures" / (name + ".bin")
            path.write_bytes(
                struct.pack("<i", len(records_chosen)) + b"".join(records_chosen)
            )
            return path, {
                "records": len(records_chosen),
                "record_bytes": 24,
                "source": "input",
                "record_offset": int(holdout),
            }

        return (
            write,
            [64, 256, 512, 1024, 2048, 4096],
            [(17, None), (64, None), (127, None)],
            [(31, None), (96, None), (129, None)],
        )
    if slug == "bucketsort":
        values = (official / "input").read_text(encoding="ascii").split()
        width, count, offset, buckets = map(int, values[:4])
        strings = values[4:]
        if len(strings) != count:
            raise RuntimeError("Official string dataset count mismatch")

        def write(count, name, holdout=False, parameter=None):
            chosen = subsample(strings, count, int(holdout))
            path = bundle / "fixtures" / (name + ".in")
            path.write_text(
                f"{width}\n{len(chosen)}\n{offset}\n{buckets}\n"
                + "\n".join(chosen)
                + "\n",
                encoding="ascii",
            )
            return path, {
                "strings": len(chosen),
                "string_width": width,
                "source": "input",
                "record_offset": int(holdout),
            }

        return (
            write,
            [512, 2048, 8192, 32768, 65536, 131072],
            [(17, None), (65, None), (257, None)],
            [(31, None), (97, None), (509, None)],
        )
    raise ValueError("Unknown supplied problem")


def prepare_problem(slug, official, output):
    root = output / "preparation" / slug
    root.mkdir(parents=True, exist_ok=False)
    bundle = root / "supplied-assets"
    bundle.mkdir()
    (bundle / "fixtures").mkdir()
    source_hashes = {}
    for p in official.rglob("*"):
        if p.is_file() and p.suffix.lower() in c.UNITS | c.HEADERS:
            target = bundle / p.relative_to(official)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(p, target)
            source_hashes[p.relative_to(official).as_posix()] = c.sha(p)
    units = sorted(
        p.relative_to(bundle).as_posix()
        for p in bundle.rglob("*")
        if p.suffix.lower() in c.UNITS
    )
    if not units:
        raise RuntimeError("No official C/C++ compilation unit")
    cpp = any(Path(p).suffix.lower() != ".c" for p in units)
    settings = {
        "language": "c++" if cpp else "c",
        "source_files": units,
        "compiler_flags": [
            "-O3",
            "-std=c++17" if cpp else "-std=c11",
            "-fopenmp",
            "-Werror=uninitialized",
            "-Werror=maybe-uninitialized",
            "-lm",
        ],
        "comparison": {
            "mode": "bytes",
            "abs_tol": 0,
            "rel_tol": 0,
            "binary_format": "",
            "basis_quote": "",
        },
    }
    c.build_source(bundle, root / "calibration-build", settings)
    writer, scales, search_sizes, confirm_sizes = fixture_writer(slug, official, bundle)
    calibration = []
    chosen = None
    for scale in scales:
        path, geometry = writer(scale, "calibration-" + str(scale))
        case = {
            "name": "calibration",
            "argv": [],
            "stdin": {"file": path.relative_to(bundle).as_posix()},
            "files": [],
            "capture_files": [],
        }
        resources = root / "calibration-resources"
        actual = c.materialize(case, bundle, resources / str(scale), resources)
        try:
            _, seconds = c.execute(
                root / "calibration-build/solution", actual, 8, resources
            )
        except c.ContractError as exc:
            calibration.append({"geometry": geometry, "diagnostic": exc.diagnostic})
            if chosen is None:
                raise
            break
        calibration.append({"geometry": geometry, "seconds": seconds})
        chosen = case
        if seconds >= 0.2:
            break
    if chosen is None:
        raise RuntimeError("No reference calibration succeeded")
    provenance = []

    def test_case(size, index, holdout, parameter):
        phase = "confirmation" if holdout else "search"
        path, geometry = writer(size, phase + "-" + str(index), holdout, parameter)
        provenance.append(
            {
                "phase": phase,
                "geometry": geometry,
                "sha256": c.sha(path),
                "bytes": path.stat().st_size,
            }
        )
        return {
            "name": phase + "-" + str(index),
            "argv": [],
            "stdin": {"file": path.relative_to(bundle).as_posix()},
            "files": [],
            "capture_files": [],
        }

    settings["search_cases"] = [
        test_case(n, i, False, s) for i, (n, s) in enumerate(search_sizes)
    ]
    settings["confirmation_cases"] = [
        test_case(n, i, True, s) for i, (n, s) in enumerate(confirm_sizes)
    ]
    settings["benchmark_case"] = {**chosen, "name": "benchmark"}
    receipt = c.prepare(settings, bundle, root / "frozen", probe_timeout=30)
    receipt.update(
        {
            "operator_prepared": True,
            "manual_algorithm_changes": 0,
            "official_source_hashes": source_hashes,
            "calibration": calibration,
            "fixtures": provenance,
            "benchmark_input_sha256": c.sha(bundle / chosen["stdin"]["file"]),
        }
    )
    c.write_json(root / "operator-preparation.json", receipt)
    return receipt
