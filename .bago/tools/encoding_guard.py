#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""encoding_guard.py -- gate de encoding para paquete BAGO."""
import sys, re
from pathlib import Path

TEXT_EXTS = {".py",".md",".json",".toml",".yaml",".yml",".txt",".sh",".ps1",".cmd",".html",".css",".js",".ts"}
_MOJIBAKE_SEQ = [
    b"\xc3\x83\xc2\xa2\xc3\xa2\xe2\x80\x9a\xc2\xac\xc3\xa2\xe2\x82\xac\xc2\x9d",
    b"\xc3\x83\xc2\xa2\xc3\xa2\xe2\x80\x9a\xc2\xac\xc3\xa2\xe2\x80\x9c",
    b"\xc3\x83\xc2\xa2\xc3\xa2\xe2\x80\x9a\xc2\xac\xc5\x92",
    b"\xc3\x83\xc2\xa2\xc3\xa2\xe2\x80\x9a\xc2\xac\xc5\x93",
    b"\xc3\x83\xc2\xa2\xc3\xa2\xe2\x80\x9a\xc2\xac\xe2\x80\x99",
    b"\xc3\x83\xc6\x92\xc2\xa9",
    b"\xc3\x83\xe2\x80\x9a\xc2\xa9",
]
_REPLACEMENT = b"\xef\xbf\xbd"
FORBIDDEN_WIN = re.compile("[" + "".join([chr(60),chr(62),chr(58),chr(34),chr(124),chr(63),chr(42)]) + "\x00-\x1f]")

def scan(root):
    errors = []
    for p in root.rglob('*'):
        if not p.is_file(): continue
        if p.name.startswith('._') or p.name == '.DS_Store': continue
        rel = str(p.relative_to(root)).replace('\\','/')
        if 'encoding_guard.py' in rel: continue
        if FORBIDDEN_WIN.search(p.name):
            errors.append(f'{rel}:1:1 nombre de archivo incompatible con Windows')
            continue
        if p.suffix.lower() not in TEXT_EXTS and p.name not in {'Makefile','bago'}: continue
        try:
            raw = p.read_bytes()
            raw.decode('utf-8')
        except UnicodeDecodeError as e:
            errors.append(f'{rel}:{e.start}:1 UnicodeDecodeError')
            continue
        if _REPLACEMENT in raw:
            pos = raw.find(_REPLACEMENT)
            before = raw[:pos]
            lineno = before.count(b'\n') + 1
            col = len(before.split(b'\n')[-1]) + 1
            errors.append(f'{rel}:{lineno}:{col} U+FFFD replacement character')
        for seq in _MOJIBAKE_SEQ:
            if seq in raw:
                pos = raw.find(seq)
                before = raw[:pos]
                lineno = before.count(b'\n') + 1
                col = len(before.split(b'\n')[-1]) + 1
                errors.append(f'{rel}:{lineno}:{col} mojibake byte sequence detected')
    return errors

if __name__ == '__main__':
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.cwd()
    errors = scan(root)
    if errors:
        print('KO encoding')
        for e in errors:
            print(e)
        sys.exit(1)
    else:
        print('GO encoding')
        sys.exit(0)
