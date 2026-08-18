#!/usr/bin/env python3
"""
_normalize_presets.py — Strip literal "\\n" inside contract text fields.
"""
import json, sys
p = sys.argv[1]
with open(p,'r',encoding='utf-8') as f:
    j = json.load(f)
for k,v in j['presets'].items():
    txt = v['contract']['text']
    # Collapse \n in JSON-escaped strings and real newlines into single space.
    txt = txt.replace(' \\n ', ' ').replace(chr(10), ' ').replace(chr(92)+'n', ' ')
    v['contract']['text'] = txt.strip()
with open(p,'w',encoding='utf-8') as f:
    json.dump(j, f, indent=2, ensure_ascii=False)
    f.write('\n')
print('normalized:', p)
