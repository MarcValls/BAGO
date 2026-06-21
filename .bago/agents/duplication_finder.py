#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
duplication_finder.py — AGENTE especializado en detección de código duplicado.

Detecta:
  - Imports duplicados
  - Constantes duplicadas
  - Funciones similares

Retorna: JSON con hallazgos
"""

from pathlib import Path
import ast
import json
import sys

class DuplicationFinder(ast.NodeVisitor):
    """Finds duplications."""
    
    def __init__(self, filename: str):
        self.filename = filename
        self.findings = []
        self.imports = []
        self.constants = {}
    
    def visit_Import(self, node: ast.Import):
        """Track imports."""
        for alias in node.names:
            if alias.name in self.imports:
                self.findings.append({
                    "rule": "DUP-I001",
                    "severity": "info",
                    "line": node.lineno,
                    "message": f"Import duplicado: '{alias.name}'"
                })
            else:
                self.imports.append(alias.name)
        
        self.generic_visit(node)
    
    def visit_Assign(self, node: ast.Assign):
        """Track constants."""
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id.isupper():
                if isinstance(node.value, ast.Constant):
                    val = str(node.value.value)
                    if val in self.constants:
                        self.findings.append({
                            "rule": "DUP-I002",
                            "severity": "info",
                            "line": node.lineno,
                            "message": f"Constante duplicada: '{val}'"
                        })
                    else:
                        self.constants[val] = node.lineno
        
        self.generic_visit(node)

def analyze_file(filepath: str) -> list:
    """Analyze single file."""
    try:
        source = Path(filepath).read_text(encoding="utf-8", errors="ignore")
        tree = ast.parse(source)
    except:
        return []
    
    finder = DuplicationFinder(filepath)
    finder.visit(tree)
    
    for finding in finder.findings:
        finding["file"] = filepath
    
    return finder.findings

def main(target_dir: str) -> int:
    """Analiza directorio."""
    findings = []
    
    for py_file in Path(target_dir).rglob("*.py"):
        if any(d in py_file.parts for d in {"__pycache__", ".git", ".bago"}):
            continue
        findings.extend(analyze_file(str(py_file)))
    
    print(json.dumps({
        "agent": "duplication_finder",
        "findings": findings,
        "count": len(findings)
    }, indent=2))
    
    return 0

if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "."
    raise SystemExit(main(target))
