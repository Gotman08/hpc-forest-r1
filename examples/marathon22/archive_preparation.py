"""Execution and independent input preparation; never an optimized candidate."""
from __future__ import annotations

import hashlib
import random
import re
import shutil
import subprocess
import zipfile
from pathlib import Path

from prepare_problem import prepare_problem as prepare_2022

from hpc_forest import contracts as c

SUBJECTS = {
    "2020-tropical": "Maximum Tropical Path Problem",
    "2020-quicksort": "Recursive Quicksort of Positive Integers",
    "2020-jacobi": "Jacobi Linear Solver Method",
    "2020-permutations": "All Permutations, Sorted",
    "2020-primes": "Yet More Primes",
    "2020-graph": "Graph Search on a DAG",
    "2021-graph": "Graph Isomorphism Detection",
    "2021-metrics": "Descriptive Statistics Metrics",
    "2021-sokoban": "Sokoban",
    "2021-johnson": "Johnson's Algorithm for SSSP",
    "2021-jacobi": "Jacobi Iterative Method for Laplace's Equation",
    "2022-knn": "k-NN", "2022-sum": "Sum", "2022-nbody": "N-body",
    "2022-bucketsort": "Bucket sort",
    "2023-sum": "Number of Submatrices that Sum to k",
    "2023-path": "Highest Sum Path in Generic Tree",
    "2023-npbonacci": "NPbonacci",
    "2023-count": "Number of Ways to Traverse a Grid",
}


def extract_sources(archive: Path, destination: Path):
    destination.mkdir(parents=True, exist_ok=False)
    with zipfile.ZipFile(archive) as z:
        for item in z.infolist():
            if item.is_dir():
                continue
            name = c.relative(item.filename)
            if (item.external_attr >> 16) & 0o170000 == 0o120000:
                raise RuntimeError("Symlink in official archive")
            # Official source only; large historical input is not required for scaled fixtures.
            if Path(name).suffix.lower() not in c.UNITS | c.HEADERS:
                continue
            if item.file_size > 256000:
                raise RuntimeError("Unbounded source unit")
            target = destination / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(z.read(item))


def text_input(key, n, seed):
    """Input-format fixtures only. Answers are always computed by the untouched oracle."""
    rng = random.Random(seed)
    if key == "2020-quicksort":
        return f"{n}\n"
    if key == "2020-permutations":
        return "".join(rng.sample("ABCDEFGHIJKL", n)) + "\n"
    if key == "2020-primes":
        first = [str(rng.randrange(101, 997)) for _ in range(n)]
        second = [str(rng.randrange(101, 997)) for _ in range(n)]
        return f"{n}\n" + "\n".join(first + second) + "\n"
    if key == "2020-graph":
        queries = [n, max(1, n // 2), max(1, n // 3)]
        lines = [f"{n} " + " ".join(map(str, queries))]
        for i in range(1, n + 1):
            neighbors = [i - 1] if i > 1 else [0]
            if i > 3:
                neighbors.append(i - rng.randrange(2, min(i, 5)))
            lines.append(f"{i} {rng.randrange(1, 100)} " + " ".join(map(str, neighbors)))
        return "\n".join(lines) + "\n"
    if key == "2020-tropical":
        colors = min(3, n)
        edges = [(i, i + 1) for i in range(n - 1)]
        edges += [(i, j) for i in range(n) for j in range(i + 2, n) if rng.random() < .5]
        return f"{n} {colors}\n" + "\n".join(str(i % colors) for i in range(n)) + f"\n{len(edges)}\n" + "\n".join(f"{i} {j}" for i, j in edges) + "\n"
    if key == "2021-graph":
        edges = {(i, i + 1) for i in range(n - 1)}
        edges |= {(i, j) for i in range(n) for j in range(i + 2, n) if rng.random() < .25}
        permutation = list(range(n))
        rng.shuffle(permutation)
        other = {(min(permutation[i], permutation[j]), max(permutation[i], permutation[j])) for i, j in edges}
        if seed % 3 == 0 and len(other) > 1:
            other.remove(sorted(other)[0])
        def graph(es):
            return f"{n}\n{len(es)}\n" + "\n".join(f"{i} {j}" for i, j in sorted(es)) + "\n"
        return graph(edges) + graph(other)
    if key == "2021-metrics":
        cols = 3 + seed % 5
        return f"{n} {cols}\n" + "\n".join(" ".join(str(rng.randrange(1, 13)) for _ in range(cols)) for _ in range(n)) + "\n"
    if key == "2021-jacobi":
        return f"{n} {37 + seed % 73}\n"
    if key == "2021-sokoban":
        boards = ["#######\n#     #\n# .$. #\n#  $  #\n#  @  #\n#######\n",
                  "#######\n#  .  #\n#  $  #\n#     #\n# @   #\n#######\n",
                  "########\n#   .  #\n#   $  #\n#      #\n# @    #\n########\n"]
        board = boards[seed % len(boards)]
        # Preserve the puzzle while varying wall padding, rotation and reflection.
        rows = board.rstrip("\n").splitlines()
        if seed % 2:
            rows = [line[::-1] for line in rows]
        if seed % 5:
            rows = list(reversed(rows))
        rows = ["#" * len(rows[0])] * (seed // 1000) + rows
        return "\n".join(rows) + "\n"
    if key == "2023-sum":
        cols = max(2, n - seed % 5)
        return f"{seed % 11 - 5} {n} {cols}\n" + "\n".join(" ".join(str(rng.randrange(-8, 9)) for _ in range(cols)) for _ in range(n)) + "\n"
    if key == "2023-path":
        lines = [str(n)]
        for i in range(n):
            children = [j for j in (2 * i + 1, 2 * i + 2) if j < n]
            lines.append(f"{rng.randrange(1, 100)} {len(children)}" + (" " + " ".join(str(j + 1) for j in children) if children else ""))
        return "\n".join(lines) + "\n"
    if key == "2023-npbonacci":
        return f"{n} {n + 11 + seed % 29}\n" + " ".join(str(rng.randrange(1, 51)) for _ in range(n)) + "\n" + " ".join(str(rng.randrange(0, 7)) for _ in range(n)) + "\n"
    if key == "2023-count":
        blocked = sorted({(rng.randrange(n), rng.randrange(n)) for _ in range(max(1, n * 2))} - {(0, 0), (n - 1, n - 1)})
        return f"{n} {len(blocked)}\n" + "\n".join(f"{i} {j}" for i, j in blocked) + "\n"
    raise ValueError("No prepared input interface for " + key)


SIZES = {
    "2020-tropical": ([4, 5, 6], [3, 4, 5]),
    "2020-quicksort": ([10000, 100000, 1000000], [7, 61, 1009]),
    "2020-permutations": ([6, 7, 8], [3, 4, 5]),
    "2020-primes": ([10, 20, 30], [3, 7, 11]),
    "2020-graph": ([500, 1500, 4000], [8, 17, 32]),
    "2021-graph": ([7, 8, 9], [4, 5, 6]),
    "2021-metrics": ([256, 512, 1024], [7, 13, 31]),
    "2021-sokoban": ([1, 2, 3], [1, 2, 3]),
    "2021-johnson": ([128, 256, 512], [8, 17, 33]),
    "2021-jacobi": ([128, 256, 512], [13, 23, 37]),
    "2023-sum": ([128, 256, 512], [3, 7, 17]),
    "2023-path": ([10000, 100000, 500000], [7, 31, 127]),
    "2023-npbonacci": ([32, 64, 96], [2, 5, 11]),
    "2023-count": ([512, 2048, 4096], [3, 17, 61]),
}


def prepare(key, official_root: Path, output: Path):
    year, slug = key.split("-", 1)
    archive = official_root / f"{year}-{slug}.zip"
    official = output / "official" / key
    if year == "2022":
        # The old interface needs its official binary input as well as source.
        official.mkdir(parents=True, exist_ok=False)
        with zipfile.ZipFile(archive) as z:
            for item in z.infolist():
                if item.is_dir():
                    continue
                name = c.relative(item.filename)
                if (item.external_attr >> 16) & 0o170000 == 0o120000:
                    raise RuntimeError("Official archive symlink")
                target = official / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(z.read(item))
        return prepare_2022(slug, official, output)
    if key == "2020-jacobi":
        # Its single printed pass/fail bit cannot independently validate the computed vector.
        # Do not certify a constant-output shortcut as an algorithmic speedup.
        raise RuntimeError("oracle_observability_insufficient: only an internal check bit is printed; no candidate generated")
    extract_sources(archive, official)
    root = output / "preparation" / key
    bundle = root / "supplied-assets"
    bundle.mkdir(parents=True, exist_ok=False)
    (bundle / "fixtures").mkdir()
    original = {}
    for p in official.rglob("*"):
        if p.is_file():
            target = bundle / p.relative_to(official)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(p, target)
            original[p.relative_to(official).as_posix()] = c.sha(p)
    units = sorted(p.relative_to(bundle).as_posix() for p in bundle.rglob("*") if p.suffix.lower() in c.UNITS)
    cpp = any(Path(p).suffix.lower() != ".c" for p in units)
    flags = ["-O3", "-std=c++17" if cpp else "-std=gnu11", "-fopenmp",
             "-Werror=uninitialized", "-Werror=maybe-uninitialized", "-lm"]
    if key == "2020-quicksort":
        flags += ["-DCOMPUTE_MD5_PROBLEM", "-lcrypto"]
    settings = {"language": "c++" if cpp else "c", "source_files": units,
                "compiler_flags": flags, "comparison": {"mode": "bytes", "abs_tol": 0,
                "rel_tol": 0, "binary_format": "", "basis_quote": ""}}
    c.build_source(bundle, root / "calibration-build", settings)
    records = []

    def fixture(n, name, seed):
        if key == "2021-johnson":
            # The input carries its own expected mean. Obtain it from the unchanged
            # reference's flushed stdout, then re-run its ORIGINAL assertion in c.prepare.
            raw = f"{n}\n{4 * n}\n0\n".encode()
            probe = subprocess.run(["stdbuf", "-o0", str(root / "calibration-build/solution")],
                                   input=raw, capture_output=True, timeout=15)
            match = re.search(rb"Mean SSSP = ([-0-9.]+)", probe.stdout)
            if not match:
                raise RuntimeError("The unchanged Johnson oracle exposes no input checksum")
            content = f"{n}\n{4 * n}\n".encode() + match[1] + b"\n"
        else:
            content = text_input(key, n, seed).encode()
        path = bundle / "fixtures" / (name + ".in")
        path.write_bytes(content)
        records.append({"name": name, "size": n, "seed": seed, "bytes": len(content),
                        "sha256": hashlib.sha256(content).hexdigest()})
        return {"name": name, "argv": [], "stdin": {"file": path.relative_to(bundle).as_posix()},
                "files": [], "capture_files": []}

    scales, tests = SIZES[key]
    calibration, chosen = [], None
    for index, size in enumerate(scales):
        case = fixture(size, f"calibration-{index}", 500 + index)
        resources = root / "calibration-resources"
        actual = c.materialize(case, bundle, resources / str(index), resources)
        try:
            _, seconds = c.execute(root / "calibration-build/solution", actual, 8, resources)
        except c.ContractError as exc:
            calibration.append({"size": size, "error": exc.diagnostic})
            if chosen is None:
                raise
            break
        chosen = case
        calibration.append({"size": size, "seconds": seconds})
        if seconds >= .2:
            break
    settings["search_cases"] = [fixture(n, f"search-{i}", 1000 + i) for i, n in enumerate(tests)]
    settings["confirmation_cases"] = [fixture(n + (0 if key == "2021-sokoban" else 1), f"confirmation-{i}", 2000 + i) for i, n in enumerate(tests)]
    settings["benchmark_case"] = {**chosen, "name": "benchmark"}
    receipt = c.prepare(settings, bundle, root / "frozen", probe_timeout=30)
    receipt.update(operator_prepared=True, manual_algorithm_changes=0,
                   official_source_hashes=original, calibration=calibration, fixtures=records,
                   benchmark_input_sha256=c.sha(bundle / chosen["stdin"]["file"]),
                   statement_url=f"http://lspd.mackenzie.br/marathon/{int(year) % 100:02d}/problemset.pdf",
                   verification_scope="exact official observable outputs; finite independent fixtures",
                   mother_may_change_tests=False)
    c.write_json(root / "operator-preparation.json", receipt)
    return receipt
