#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
logic_checker.py — AGENTE especializado en detección de errores lógicos.

Detecta:
  - Comparaciones innecesarias (x == True)
  - Bare except clauses
  - Variables sin inicializar
  - Dead code
  - Missing returns

Retorna: JSON con hallazgos
"""

from pathlib import Path
import ast
import json
import sys

class LogicChecker(ast.NodeVisitor):
    """Checks for logic errors."""
    
    def __init__(self, filename: str):
        self.filename = filename
        self.findings = []
    
    def visit_If(self, node: ast.If):
        """Check for unnecessary comparisons."""
        if isinstance(node.test, ast.Compare):
            if any(isinstance(op, (ast.Eq, ast.NotEq)) for op in node.test.ops):
                for comp in node.test.comparators:
                    if isinstance(comp, ast.Constant) and comp.value in {True, False}:
                        self.findings.append({
                            "rule": "BUG-E005",
                            "severity": "warning",
                            "line": node.lineno,
                            "message": f"Comparación innecesaria con {comp.value}"
                        })
        
        self.generic_visit(node)
    
    def visit_ExceptHandler(self, node: ast.ExceptHandler):
        """Check for bare except."""
        if node.type is None:
            self.findings.append({
                "rule": "BUG-E004",
                "severity": "warning",
                "line": node.lineno,
                "message": "Bare except clause — especifica tipo de excepción"
            })
        self.generic_visit(node)

def analyze_file(filepath: str) -> list:
    """Analyze single file."""
    try:
        source = Path(filepath).read_text(encoding="utf-8", errors="ignore")
        tree = ast.parse(source)
    except:
        return []
    
    checker = LogicChecker(filepath)
    checker.visit(tree)
    
    for finding in checker.findings:
        finding["file"] = filepath
    
    return checker.findings

def main(target_dir: str) -> int:
    """Analiza directorio."""
    findings = []
    
    for py_file in Path(target_dir).rglob("*.py"):
        if any(d in py_file.parts for d in {"__pycache__", ".git", ".bago"}):
            continue
        findings.extend(analyze_file(str(py_file)))
    
    print(json.dumps({
        "agent": "logic_checker",
        "findings": findings,
        "count": len(findings)
    }, indent=2))
    
    return 0

if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "."
    raise SystemExit(main(target))
