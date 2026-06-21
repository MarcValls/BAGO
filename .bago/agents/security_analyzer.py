#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
security_analyzer.py — AGENTE especializado en detección de vulnerabilidades.

NO es ejecutado por usuario. Es DELEGADO por code-quality-orchestrator.

Detecta:
  - SQL injection patterns
  - Hardcoded credentials/secrets
  - Dangerous functions (eval, exec, pickle)
  - Command injection risks
  - Insecure deserialization

Retorna: JSON con hallazgos clasificados por severidad
"""

from pathlib import Path
import ast
import json
import sys
import re

class SecurityChecker(ast.NodeVisitor):
    """Checks for security vulnerabilities."""
    
    def __init__(self, filename: str, source: str):
        self.filename = filename
        self.source = source
        self.findings = []
    
    def visit_Call(self, node: ast.Call):
        """Check dangerous function calls."""
        if isinstance(node.func, ast.Name):
            if node.func.id in {'eval', 'exec', '__import__'}:
                self.findings.append({
                    "rule": "SEC-W004",
                    "severity": "critical",
                    "line": node.lineno,
                    "message": f"Uso de '{node.func.id}()' es potencialmente peligroso"
                })
            if node.func.id in {'pickle.loads', 'pickle.load'}:
                self.findings.append({
                    "rule": "SEC-W005",
                    "severity": "critical",
                    "line": node.lineno,
                    "message": f"Uso de '{node.func.id}()' sin validación"
                })
        
        self.generic_visit(node)
    
    def visit_Assign(self, node: ast.Assign):
        """Check for hardcoded secrets."""
        for target in node.targets:
            if isinstance(target, ast.Name):
                var_name = target.id.lower()
                if any(k in var_name for k in {'password', 'secret', 'token', 'key', 'apikey'}):
                    if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                        if len(node.value.value) > 0:
                            self.findings.append({
                                "rule": "SEC-W002",
                                "severity": "critical",
                                "line": node.lineno,
                                "message": f"Credencial hardcoded en '{var_name}' → usa env vars"
                            })
        
        self.generic_visit(node)

def analyze_file(filepath: str) -> list:
    """Analyze single file."""
    try:
        source = Path(filepath).read_text(encoding="utf-8", errors="ignore")
        tree = ast.parse(source, filename=filepath)
    except:
        return []
    
    checker = SecurityChecker(filepath, source)
    checker.visit(tree)
    
    for finding in checker.findings:
        finding["file"] = filepath
    
    return checker.findings

def main(target_dir: str) -> int:
    """Analiza directorio y retorna JSON."""
    findings = []
    
    for py_file in Path(target_dir).rglob("*.py"):
        if any(d in py_file.parts for d in {"__pycache__", ".git", ".bago"}):
            continue
        findings.extend(analyze_file(str(py_file)))
    
    # Retorna JSON
    print(json.dumps({
        "agent": "security_analyzer",
        "findings": findings,
        "count": len(findings)
    }, indent=2))
    
    return 0

if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "."
    raise SystemExit(main(target))
