#!/usr/bin/env python3
"""Recover the exact approved export without regenerating recipes."""
import argparse,gzip,hashlib,json,shutil
from pathlib import Path
root=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--output',type=Path,default=root/'data/snapp_typesense_documents.jsonl');a=p.parse_args();a.output.parent.mkdir(parents=True,exist_ok=True)
artifact=root/'deploy/artifacts';manifest=json.loads((artifact/'recipe_index_manifest.json').read_text())
with gzip.open(artifact/manifest['artifact'],'rb') as src,a.output.open('wb') as dst:shutil.copyfileobj(src,dst)
assert hashlib.sha256(a.output.read_bytes()).hexdigest()==manifest['uncompressed_sha256'],'Approved corpus hash mismatch'
print('Approved recipe export recovered:28522 documents; SHA256 verified')
