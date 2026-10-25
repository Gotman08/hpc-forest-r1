"""Inspect the measured CPU binaries after timing, without replacing them."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    root = Path(__file__).resolve().parent
    out = root / ('measurements-' + os.environ['SLURM_JOB_ID']) / 'binary-audit'
    out.mkdir()
    records = []
    for item in json.loads((root / 'manifest.json').read_text()):
        if item.get('missing'):
            continue
        directory = root / item['case_id'] / item['variant']
        source = directory / 'candidate.cpp'
        binary = directory / 'candidate.so'
        assert digest(source) == item['sha256']
        original = digest(binary)
        stem = item['case_id'] + '-' + item['variant']
        record = {'case': item['case_id'], 'variant': item['variant'],
                  'source_sha256': digest(source), 'binary_sha256': original,
                  'audit_only': item.get('audit_only', False)}
        if not item.get('audit_only'):
            record['measured_binary_sha256'] = original
        if shutil.which('objdump'):
            result = subprocess.run(['objdump', '-d', '-C', str(binary)],
                                    capture_output=True, text=True, timeout=60)
            (out / (stem + '-assembly.txt')).write_text(result.stdout + result.stderr)
            record['objdump_returncode'] = result.returncode
        else:
            record['objdump_unavailable'] = True
        # Diagnostic compilation only. This output is never benchmarked or loaded.
        rebuilt = out / (stem + '-diagnostic.so')
        vector_log = out / (stem + '-vectorization.txt')
        command = ['g++', '-std=c++17', '-O3', '-march=native', '-fPIC', '-shared',
                   '-fopenmp', '-Wl,-Bsymbolic', '-fopt-info-vec-all=' + str(vector_log),
                   str(source), '-o', str(rebuilt)]
        result = subprocess.run(command, capture_output=True, text=True, timeout=120)
        (out / (stem + '-diagnostic-build.txt')).write_text(result.stdout + result.stderr)
        record.update(command=command, diagnostic_returncode=result.returncode)
        if result.returncode == 0:
            record['diagnostic_binary_sha256'] = digest(rebuilt)
            record['identical_to_original_binary'] = digest(rebuilt) == original
        assert digest(binary) == original, 'The measured binary must remain unchanged'
        record['original_binary_unchanged'] = True
        records.append(record)
    (out / 'manifest.json').write_text(json.dumps({
        'purpose': 'Post-timing compiler diagnostics; no change to measured inputs or binaries',
        'caution': 'Vector instructions or an optimized-loop message do not by themselves prove hot-loop speedup',
        'records': records}, indent=2))
    print('BINARY_AUDIT_DONE', len(records), flush=True)


if __name__ == '__main__':
    main()
