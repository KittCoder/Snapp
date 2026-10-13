#!/usr/bin/env python3
"""Safe static/history checks. Reports locations/types, never secret values."""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
PATTERNS={
 'private_key':re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'),
 'provider_key':re.compile(r'\bsk-(?:proj-)?[A-Za-z0-9_-]{24,}'),
 'github_token':re.compile(r'\bgh[pousr]_[A-Za-z0-9]{30,}'),
 'aws_access_key':re.compile(r'\bAKIA[0-9A-Z]{16}'),
 'credential_assignment':re.compile(r'''(?i)(?:TYPESENSE_API_KEY|SUPABASE_SERVICE_ROLE_KEY|SNAPP_ADMIN_TOKEN|OPENAI_API_KEY)\s*[:=]\s*["']([A-Za-z0-9_.-]{24,})["']'''),
 'credential_url':re.compile(r'\b(?:postgres(?:ql)?|rediss?|https?)://[^\s/:]+:[^\s/@]+@'),
 'service_role_jwt':re.compile(r'eyJ[A-Za-z0-9_-]+\.eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+'),
}

def findings(text,location):
    result=[]
    for kind,pattern in PATTERNS.items():
        for match in pattern.finditer(text):
            if kind=='credential_url' and location=='Web/tests/shopping_deals.test.cjs' and match.group().endswith('user:password@'):continue  # Explicit hostile-link regression fixture.
            if kind=='service_role_jwt':
                import base64
                try:
                    part=match.group().split('.')[1];claims=json.loads(base64.urlsafe_b64decode(part+'='*(-len(part)%4)))
                    if claims.get('role')!='service_role':continue
                except Exception:continue
            result.append({'file':location,'type':kind,'line':text.count('\n',0,match.start())+1,'preview':'[redacted]'})
    return result


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--history',action='store_true');parser.add_argument('--output',type=Path);args=parser.parse_args()
    tracked=subprocess.check_output(['git','ls-files','-z'],cwd=ROOT).decode().split('\0')
    hits=[]
    for name in filter(None,tracked):
        p=ROOT/name
        if p.is_file():
            try:hits.extend(findings(p.read_text(),name))
            except UnicodeError:pass
    # Include untracked browser assets and application modules; ignore local secrets/corpora.
    checked=set(tracked)
    for directory in ['Web','Model','scripts','supabase']:
        for p in (ROOT/directory).rglob('*'):
            name=str(p.relative_to(ROOT))
            if name in checked or p.suffix not in {'.py','.js','.cjs','.html','.sql'} or any(v in p.parts for v in ['node_modules','__pycache__']):continue
            hits.extend(findings(p.read_text(),name))
    local_secret_locations=[]
    for p in list(ROOT.glob('.env*'))+list((ROOT/'Model').glob('.env*')):
        if p.name.endswith('.example') or not p.is_file():continue
        raw=p.read_text()
        for key,value in re.findall(r'^([A-Z_]+)=(.+)$',raw,re.M):
            if re.search(r'TOKEN|PASSWORD|SECRET|API_KEY|SERVICE_ROLE',key) and len(value.strip())>=16:
                local_secret_locations.append({'file':str(p.relative_to(ROOT)),'type':key,'preview':'[redacted]','tracked':str(p.relative_to(ROOT)) in tracked})
    if args.history:
        # Scan every retained commit's full tracked tree, including files since deleted.
        commits=subprocess.check_output(['git','rev-list','--all'],cwd=ROOT).decode().splitlines()
        for commit in commits:
            changes=subprocess.check_output(['git','show','--format=','--no-ext-diff',commit],cwd=ROOT).decode(errors='replace')
            hits.extend(findings(changes,'git-history:'+commit[:12]))
    vercel=json.loads((ROOT/'vercel.json').read_text());headers={h['key']:h['value'] for row in vercel.get('headers',[]) for h in row['headers']}
    failures=[]
    for key in ['Content-Security-Policy','X-Content-Type-Options','Referrer-Policy','Permissions-Policy','Strict-Transport-Security']:
        if key not in headers:failures.append('Missing frontend header '+key)
    if "frame-ancestors 'none'" not in headers.get('Content-Security-Policy',''):failures.append('Missing frame protection')
    if 'unsafe-eval' in headers.get('Content-Security-Policy','') or "script-src 'self' 'unsafe-inline'" in headers.get('Content-Security-Policy',''):failures.append('Unsafe script CSP')
    model=(ROOT/'Model/model.py').read_text();frontend=(ROOT/'Web/app.js').read_text()
    if '"*" in CORS_ORIGINS' in model:failures.append('Wildcard CORS enabled')
    if re.search(r'app.run\([^\n]*debug=True',model):failures.append('Debug server enabled')
    if re.search(r'\.innerHTML\s*=|insertAdjacentHTML\(',frontend):failures.append('Unsafe HTML sink requires review')
    if 'install_security(app)' not in model:failures.append('Request guard missing')
    if 'python security_config.py && gunicorn' not in (ROOT/'render.yaml').read_text():failures.append('Production preflight missing')
    for pattern in ['SUPABASE_SERVICE_ROLE','TYPESENSE_API_KEY','SNAPP_ADMIN_TOKEN']:
        if pattern in frontend:failures.append('Privileged credential reference in browser '+pattern)
    report={'secret_findings':hits,'local_secret_locations':local_secret_locations,'static_failures':failures,'history_scanned':args.history,'limitations':'Pattern scan is not exhaustive; live cloud/RLS configuration and secret rotation require operator verification.'}
    if args.output:args.output.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2));return 1 if failures or hits else 0
if __name__=='__main__':sys.exit(main())
