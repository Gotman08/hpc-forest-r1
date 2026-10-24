"""Check published data/links and JavaScript syntax without executing a web page."""
import csv
import datetime
import hashlib
import json
from html.parser import HTMLParser
from pathlib import Path
import re
import shutil
import subprocess

R = Path(__file__).resolve().parent
O = R.parents[1] / 'outputs/architecture-active'


class Structure(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = set()
        self.links = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if 'id' in attrs:
            assert attrs['id'] not in self.ids, attrs['id']
            self.ids.add(attrs['id'])
        if tag == 'a' and 'href' in attrs:
            self.links.append(attrs['href'])


def main():
    data = json.loads((O / 'RESULTATS.json').read_text(encoding='utf8'))
    page = (O / 'TABLEAU-DE-BORD.html').read_text(encoding='utf8')
    structure = Structure()
    structure.feed(page)
    for link in structure.links:
        assert ':' not in link and (O / link).is_file(), link
    markdown_links = 0
    for path in O.glob('*.md'):
        for link in re.findall(r'\]\(([^)]+)\)', path.read_text(encoding='utf8')):
            if '://' in link or link.startswith('#'):
                continue
            link = link.split('#', 1)[0]
            # Before publication, the future mesures/ directory is still in R.
            target = R / link[len('mesures/'):] if link.startswith('mesures/') else O / link
            assert target.is_file(), (path.name, link)
            markdown_links += 1
    script = re.search(r'<script>(.*?)</script>', page, re.S).group(1)
    payload = re.search(r'^const data=(.*);\nconst esc=', script).group(1)
    assert json.loads(payload) == {k: data[k] for k in ['summary', 'rows', 'engines']}
    check = R / 'dashboard-syntax-check.js'
    check.write_text(script, encoding='utf8')
    node = shutil.which('node')
    assert node, 'Node.js is required for the static syntax check'
    subprocess.run([node, '--check', str(check)], check=True, capture_output=True)
    counts = {}
    for name, key in [('COMPARAISON', 'rows'), ('CAMPAGNES', 'engines'), ('ESSAIS', 'trials'),
                      ('ARBRES', 'trees'), ('APPELS-ANALYSTES-MOTHER', 'calls'),
                      ('DECISIONS', 'decisions'), ('CHRONOLOGIE', 'chronology'),
                      ('TENTATIVES-PREALABLES', 'setup_attempts'), ('ENVIRONNEMENTS', 'environments'),
                      ('REFERENCES-LES-PLUS-RAPIDES', 'strongest_references')]:
        with (O / (name + '.csv')).open(encoding='utf-8-sig', newline='') as stream:
            records = list(csv.DictReader(stream))
        assert len(records) == len(data[key]), (name, len(records), len(data[key]))
        counts[name] = len(records)
    resources = json.loads((O / 'RESSOURCES-SLURM.json').read_text(encoding='utf8'))
    with (O / 'RESSOURCES-SLURM.csv').open(encoding='utf-8-sig', newline='') as stream:
        resource_rows = list(csv.DictReader(stream))
    assert len(resource_rows) == len(resources['records'])
    assert len({r['job_id'] for r in resource_rows}) == len(resource_rows)
    completed_jobs = {str(e['job_id']) for e in data['engines'] if e['period'] == 'new' and e['pipeline_complete']}
    resource_jobs = {r['job_id'] for r in resource_rows if r['scope'] == 'active_search_selected'}
    assert completed_jobs == resource_jobs, (completed_jobs, resource_jobs)
    setup_jobs = {str(a['job_id']) for a in data['setup_attempts']}
    all_resource_jobs = {r['job_id'] for r in resource_rows}
    assert setup_jobs <= all_resource_jobs, setup_jobs - all_resource_jobs
    counts['RESSOURCES-SLURM'] = len(resource_rows)
    result = {'at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'static_validation_passed': True, 'unique_html_ids': len(structure.ids),
              'local_links_checked': len(structure.links), 'csv_rows_checked': counts,
              'markdown_links_checked': markdown_links,
              'javascript_syntax': 'node --check passed', 'embedded_json_matches': True,
              'browser_preview': 'unavailable: browser policy denied file protocol; no workaround attempted',
              'visual_dashboard_validation': False,
              'html_sha256': hashlib.sha256(page.encode('utf8')).hexdigest()}
    (R / 'dashboard-validation.json').write_text(json.dumps(result, indent=2), encoding='utf8')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
