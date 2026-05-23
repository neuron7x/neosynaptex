from __future__ import annotations
import re,sys,json
from pathlib import Path
patterns=[r'/home/',r'AKIA[0-9A-Z]{16}',r'ghp_[A-Za-z0-9]{20,}',r'private',r'localhost']
find=[]; root=Path('evidence')
if root.exists():
  for p in root.rglob('*'):
    if not p.is_file(): continue
    t=p.read_text(encoding='utf-8',errors='ignore')
    for pat in patterns:
      if re.search(pat,t): find.append({'file':str(p),'pattern':pat}); break
out=Path('artifacts/package/evidence_leakage_scan.json'); out.parent.mkdir(parents=True,exist_ok=True)
out.write_text(json.dumps({'findings':find},indent=2),encoding='utf-8')
if find: print(f'leakage findings: {len(find)}'); sys.exit(1)
print('leakage-scan: OK')
