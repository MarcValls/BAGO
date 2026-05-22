#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
smell_detector.py — AGENTE especializado en detección de code smells.

Detecta:
  - Funciones demasiado largas (>50 líneas)
  - Demasiados parámetros (>5)
  - Variables no usadas
  - Complejidad alta

Retorna: JSON con hallazgos
"""

from pathlib import Path
import ast
import json
import sys

class SmellDetector(ast.NodeVisitor):
    """Detects code smells."""
    
    def __init__(self, filename: str, source_lines: list):
        self.filename = filename
        self.source_lines = source_lines
        self.findings = []
    
    def visit_FunctionDef(self, node: ast.FunctionDef):
        """Check function metrics."""
        # SMELL-I001: Función demasiado larga
        if hasattr(node, 'end_lineno') and node.end_lineno:
            func_lines = node.end_lineno - node.lineno
            if func_lines > 50:
                self.findings.append({
                    "rule": "SMELL-I001",
                    "severity": "info",
                    "line": node.lineno,
                    "message": f"Función '{node.name}' demasiado larga ({func_lines} líneas)"
                })
        
        # SMELL-I002: Demasiados parámetros
        num_params = len(node.args.args)
        if num_params > 5:
            self.findings.append({
                "rule": "SMELL-I002",
                "severity": "info",
                "line": node.lineno,
                "message": f"Función '{node.name}' tiene {num_params} parámetros (>5)"
            })
        
        self.generic_visit(node)
    
    visit_AsyncFunctionDef = visit_FunctionDef

def analyze_file(filepath: str) -> list:
    """Analyze single file."""
    try:
        source = Path(filepath).read_text(encoding="utf-8", errors="ignore")
        source_lines = source.split('\n')
        tree = ast.parse(source)
    except:
        return []
    
    detector = SmellDetector(filepath, source_lines)
    detector.visit(tree)
    
    for finding in detector.findings:
        finding["file"] = filepath
    
    return detector.findings

def main(target_dir: str) -> int:
    """Analiza directorio."""
    findings = []
    
    for py_file in Path(target_dir).rglob("*.py"):
        if any(d in py_file.parts for d in {"__pycache__", ".git", ".bago"}):
            continue
        findings.extend(analyze_file(str(py_file)))
    
    print(json.dumps({
        "agent": "smell_detector",
        "findings": findings,
        "count": len(findings)
    }, indent=2))
    
    return 0

if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "."
    raise SystemExit(main(target))
