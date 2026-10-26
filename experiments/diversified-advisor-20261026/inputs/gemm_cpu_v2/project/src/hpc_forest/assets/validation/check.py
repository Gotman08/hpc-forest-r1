"""Controller-owned full-matrix oracle, independent from the C kernel."""

import json
import subprocess
import sys


def expected(n, seed):
    a = [[(i * 17 + j * 3 + seed) % 13 - 6 for j in range(n)] for i in range(n)]
    b = [[(i * 5 + j * 11 + seed * 2) % 17 - 8 for j in range(n)] for i in range(n)]
    return [sum(a[i][k] * b[k][j] for k in range(n)) for i in range(n) for j in range(n)]


def main():
    binary, phase = sys.argv[1:3]
    cases = [(1, 0), (3, 7), (17, 19), (33, 23)]
    if phase == "confirmation":
        cases = [(2, 99), (5, 103), (19, 107), (37, 109)]
    try:
        for n, seed in cases:
            for repeats in [1, 2]:
                process = subprocess.run(
                    [binary, str(n), str(seed), str(repeats), "full"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                    check=True,
                )
                output = json.loads(process.stdout)
                oracle = expected(n, seed)
                if output["n"] != n or output["matrix"] != oracle:
                    raise ValueError(
                        f"Full matrix mismatch for n={n}, seed={seed}, repeats={repeats}"
                    )
                if output["checksum"] != sum(x * (1 + i % 7) for i, x in enumerate(oracle)):
                    raise ValueError("Checksum mismatch")
    except (ValueError, KeyError, subprocess.SubprocessError, OSError) as exc:
        print(json.dumps({"correct": False, "cases": 0, "reason": str(exc)}))
        return 1
    print(json.dumps({"correct": True, "cases": len(cases) * 2, "phase": phase}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
