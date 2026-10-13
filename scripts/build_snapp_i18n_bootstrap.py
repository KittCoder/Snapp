"""Compile the canonical English/locale manifest bootstrap, without a build stack."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
directory=ROOT/'Web/i18n'
text='window.SNAPP_EN_CATALOG = '+json.dumps(json.loads((directory/'en.json').read_text()),ensure_ascii=False)+';\n'
text+='window.SNAPP_LOCALE_MANIFEST = '+json.dumps(json.loads((directory/'locales.json').read_text()),ensure_ascii=False)+';\n'
(directory/'catalog.js').write_text(text)
