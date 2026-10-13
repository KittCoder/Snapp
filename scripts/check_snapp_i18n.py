"""Offline coverage/placeholder check for all shipped locale resources."""
import json,re,sys
from html.parser import HTMLParser
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];DIRECTORY=ROOT/'Web/i18n'
LOCALES=list(json.loads((DIRECTORY/'locales.json').read_text()))
def check():
 en=json.loads((DIRECTORY/'en.json').read_text());errors=[]
 for locale in LOCALES:
  path=DIRECTORY/f'{locale}.json'
  if not path.exists():errors.append(f'Missing locale {locale}');continue
  copy=json.loads(path.read_text())
  for key,value in en.items():
   if not isinstance(copy.get(key),str) or not copy[key].strip():errors.append(f'{locale}: missing {key}');continue
   if set(re.findall(r'\{\w+\}',value))!=set(re.findall(r'\{\w+\}',copy[key])):errors.append(f'{locale}: placeholder mismatch {key}')
 class Bindings(HTMLParser):
  def handle_starttag(self,tag,attrs):
   for name,key in attrs:
    if name=='data-i18n' or (name.startswith('data-i18n-') and name.endswith('-key')):
     if key not in en:errors.append(f'HTML missing key {key}')
 Bindings().feed((ROOT/'Web/index.html').read_text())
 source=(ROOT/'Web/app.js').read_text()
 for key in re.findall(r'\bt\(["\']([^"\']+)',source):
  if key not in en:errors.append(f'JS missing key {key}')
 for match in re.finditer(r'\.textContent\s*=\s*(["\'])([A-Z][^"\']{3,})\1',source):errors.append('Unkeyed dynamic UI copy: '+match[2])
 expected='window.SNAPP_EN_CATALOG = '+json.dumps(en,ensure_ascii=False)+';\n'
 expected+='window.SNAPP_LOCALE_MANIFEST = '+json.dumps(json.loads((DIRECTORY/'locales.json').read_text()),ensure_ascii=False)+';\n'
 if (DIRECTORY/'catalog.js').read_text()!=expected:errors.append('English bootstrap is out of sync with en.json')
 return en,errors
if __name__=='__main__':
 en,errors=check()
 print(f'{len(en)} keys × {len(LOCALES)} locales; {len(errors)} coverage errors')
 for error in errors:print(error)
 sys.exit(bool(errors))
