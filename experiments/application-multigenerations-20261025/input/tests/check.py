import subprocess
import sys

executable = sys.argv[1]
limits = [0, 1, 2, 3, 4, 10, 97, 100, 997, 1024, 4096, 7919, 12000, 20000]
for limit in limits:
    candidates = [True] * (limit + 1)
    for p in range(2, limit + 1):
        if candidates[p]:
            for q in range(p * p, limit + 1, p):
                candidates[q] = False
    expected = sum(n for n in range(2, limit + 1) if candidates[n])
    result = subprocess.run([executable, str(limit)], capture_output=True, text=True, check=True)
    assert result.stdout == str(expected) + "\n", (limit, result.stdout, expected)
for invalid in [-1, 200001]:
    assert subprocess.run([executable, str(invalid)], capture_output=True).returncode == 2
print("16 correctness cases passed")
