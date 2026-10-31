"""Controller-owned full-matrix oracle, independent from the C kernel."""

import json
import os
import subprocess
import sys

SEEDS = "FOREST_CONFIRMATION_SEEDS"


def confirmation_cases():
    """Sizes are public; seeds drawn by the controller at confirmation are not.

    Without drawn seeds (protocol 1), the historical fixed cases apply.
    """
    drawn = os.environ.get(SEEDS)
    seeds = [int(value) for value in drawn.split(",")] if drawn else [99, 103, 107, 109]
    return list(zip([2, 5, 19, 37], seeds, strict=True))


def expected(n, seed):
    a = [[(i * 17 + j * 3 + seed) % 13 - 6 for j in range(n)] for i in range(n)]
    b = [[(i * 5 + j * 11 + seed * 2) % 17 - 8 for j in range(n)] for i in range(n)]
    return [sum(a[i][k] * b[k][j] for k in range(n)) for i in range(n) for j in range(n)]


def main():
    binary, phase = sys.argv[1:3]
    cases = [(1, 0), (3, 7), (17, 19), (33, 23)]
    if phase == "confirmation":
        cases = confirmation_cases()
    # The candidate never sees the drawn seeds in its own environment.
    env = {key: value for key, value in os.environ.items() if key != SEEDS}
    try:
        for n, seed in cases:
            for repeats in [1, 2]:
                process = subprocess.run(
                    [binary, str(n), str(seed), str(repeats), "full"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                    check=True,
                    env=env,
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
    print(json.dumps({"correct": True, "cases": len(cases) * 2, "phase": phase,
                      "seeds": [seed for _, seed in cases]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
