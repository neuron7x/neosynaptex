#!/usr/bin/env python3
from __future__ import annotations
import json
from pathlib import Path
import yaml

ROOT = Path('.')
SPEC = ROOT / 'docs/research/07_first_principles_value_function.yaml'
OUT = ROOT / 'artifacts/audit/value_architecture_report.json'


def main() -> int:
    data = yaml.safe_load(SPEC.read_text(encoding='utf-8'))
    checks = []
    for domain, payload in data.get('architecture_mapping', {}).items():
        for artifact in payload.get('artifacts', []):
            p = ROOT / artifact
            ok = p.exists() and p.stat().st_size > 0
            checks.append({'domain': domain, 'artifact': artifact, 'status': 'PASS' if ok else 'FAIL'})
    status = 'PASS' if all(c['status']=='PASS' for c in checks) else 'FAIL'
    report = {
        'check_id': 'ARCH-01',
        'protocol_id': data.get('protocol_id'),
        'status': status,
        'objective': data.get('objective'),
        'checks': checks,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2, ensure_ascii=False)+'\n', encoding='utf-8')
    print(OUT)
    return 0 if status=='PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
