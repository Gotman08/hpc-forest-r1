"""After all SLURM study stages: recover evidence, remeasure and export tables."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

from analyze_controlled import analyze

from hpc_forest.core import atomic_json, file_digest


def extract(archive, destination):
    # Archives are our own jobs' output, but still reject traversal and unsafe links.
    with tarfile.open(archive) as stream:
        stream.extractall(destination, filter='data')


def finish(bundle, output):
    if not os.environ.get('SLURM_JOB_ID'):
        raise RuntimeError('The post-study compute allocation is required')
    output.mkdir(parents=True, exist_ok=False)
    protocol = json.loads((bundle / 'protocol.json').read_text(encoding='utf8'))
    if file_digest(bundle / 'heldout-protocol.json') != protocol['reserved_protocol_sha256']:
        raise RuntimeError('Registered reserved inputs changed')
    specs = json.loads((bundle / 'blocks.json').read_text(encoding='utf8'))
    temporary = Path(tempfile.mkdtemp(prefix='forest-common-'))
    persistent = os.environ.get('FOREST_PERSISTENT_BLOCKS') == '1'
    blocks, archives = [], []
    for spec in specs:
        block = Path(spec['remote_root']) if persistent else temporary / spec['pair_id']
        if file_digest(Path(spec['remote_archive'])) != spec['sha256']:
            raise RuntimeError('Frozen search payload changed')
        if not persistent or not block.exists():
            block.mkdir(parents=True)
            extract(spec['remote_archive'], block)
        else:
            frozen_files = json.loads((block / 'files.json').read_text(encoding='utf8'))
            for name, expected in frozen_files.items():
                if file_digest(block / name) != expected:
                    raise RuntimeError('Persistent frozen payload changed: ' + name)
        archive = Path(spec['remote_root'] + '.results.tar.gz')
        if persistent:
            receipts = [json.loads(p.read_text(encoding='utf8')) for p in block.glob('*-preservation.json')]
            for receipt in receipts:
                if file_digest(Path(receipt['archive'])) != receipt['archive_sha256']:
                    raise RuntimeError('Settled evidence archive changed')
            archives.append({'block': spec['pair_id'], 'persistent_root': str(block), 'settled_archives': receipts})
        elif archive.exists():
            archives.append({'block': spec['pair_id'], 'archive_sha256': file_digest(archive)})
            extract(archive, block)
        else:
            archives.append({'block': spec['pair_id'], 'archive_missing': True})
        atomic_json(block / 'scheduler-finished.json', {'common_job': os.environ['SLURM_JOB_ID'],
            'dependency': 'afterany of all four independent search blocks', 'partial_archive_allowed': True})
        blocks.append(block)
    atomic_json(output / 'recovered-archives.json', archives)
    statuses = {}
    try:
        for distribution in ('registered', 'reserved'):
            args = [sys.executable, str(bundle / 'remeasure_all.py'), '--pairs', *map(str, blocks),
                    '--output', str(output / distribution)]
            if distribution == 'reserved':
                args += ['--heldout-protocol', str(bundle / 'heldout-protocol.json'),
                         '--heldout-sha256', protocol['reserved_protocol_sha256']]
            with (output / (distribution + '.log')).open('wb') as stream:
                try:
                    result = subprocess.run(args, stdout=stream, stderr=subprocess.STDOUT, timeout=5400)
                    statuses[distribution] = result.returncode
                except subprocess.TimeoutExpired:
                    statuses[distribution] = 124
            atomic_json(output / 'measurement-statuses.json', statuses)
        summary = analyze(blocks, output / 'comparison',
            output / 'registered/common-measurements.json', output / 'reserved/common-measurements.json')
        complete = (all(v == 0 for v in statuses.values()) and not summary['audit_errors']
                    and summary['delivered'] == summary['assigned_arms'])
        atomic_json(output / 'completion.json', {'scheduler_job': os.environ['SLURM_JOB_ID'],
            'measurement_statuses': statuses, 'analysis': summary,
            'complete': complete})
        return 0 if complete else 1
    finally:
        # Preserve reconstructed campaigns too; do not rely on /tmp after job exit.
        if not persistent:
            subprocess.run(['tar', '-czf', str(output) + '.recovered.tar.gz', '-C', str(temporary), '.'],
                           check=True, timeout=900)
        subprocess.run(['tar', '-czf', str(output) + '.results.tar.gz', '-C', str(output), '.'],
                       check=True, timeout=900)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--bundle', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    raise SystemExit(finish(args.bundle.resolve(), args.output.resolve()))
