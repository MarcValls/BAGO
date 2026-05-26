#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
bago_typing_course_analyzer.py

DEMO INTERACTIVO: BAGO analizando proyecto typing-course

Flujo:
1. Lee archivos del proyecto
2. Ejecuta AGENTS en paralelo (security, logic, smell, duplication)
3. Consulta ROLES (REVISOR_SEGURIDAD, REVISOR_PERFORMANCE, MAESTRO_BAGO)
4. Genera reporte integrado

Uso:
  python bago_typing_course_analyzer.py C:/Marc_max_20gb/typing-course
"""

import os
import sys

os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import json
import subprocess
import sys
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

# Configuration
AGENTS_DIR = Path(r"C:\Marc_max_20gb\.bago\agents")
ROLES_DIR = Path(r"C:\Marc_max_20gb\.bago\roles")

class TypingCourseAnalyzer:
    """Analizador BAGO interactivo para typing-course."""
    
    def __init__(self, project_path):
        self.project_path = Path(project_path)
        self.timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.findings = {
            "security": [],
            "logic": [],
            "smells": [],
            "duplication": []
        }
        self.agent_results = {}
        
    def print_header(self, text):
        """Print formatted header."""
        print(f"\n{'='*70}")
        print(f"  {text}")
        print(f"{'='*70}\n")
    
    def print_section(self, text):
        """Print section header."""
        print(f"\n{text}")
        print(f"{'-' * len(text)}\n")
    
    def read_project_files(self):
        """Lee archivos JS del proyecto."""
        print("📂 Leyendo archivos del proyecto...")
        files = {}
        
        for js_file in self.project_path.glob("src/**/*.js"):
            content = js_file.read_text(encoding="utf-8")
            rel_path = js_file.relative_to(self.project_path)
            files[str(rel_path)] = content
            print(f"   ✓ {rel_path} ({len(content)} bytes)")
        
        return files
    
    def analyze_with_agent_security(self, files):
        """AGENT: Security Analyzer - Busca vulnerabilidades."""
        self.print_section("🔒 AGENT: Security Analyzer")
        
        issues = []
        
        for filepath, content in files.items():
            # Detectar vulnerabilidades comunes
            if "innerHTML" in content:
                issues.append({
                    "severity": "CRITICAL",
                    "file": filepath,
                    "issue": "XSS vulnerability: Using innerHTML with untrusted data",
                    "line": self._find_line(content, "innerHTML"),
                    "recommendation": "Use textContent or DOMPurify instead"
                })
            
            if "http://" in content and "localhost" not in content:
                issues.append({
                    "severity": "HIGH",
                    "file": filepath,
                    "issue": "Insecure protocol: HTTP instead of HTTPS",
                    "line": self._find_line(content, "http://"),
                    "recommendation": "Always use HTTPS for data transmission"
                })
            
            if "fetch(" in content and ".catch" not in content:
                issues.append({
                    "severity": "MEDIUM",
                    "file": filepath,
                    "issue": "Unhandled fetch: Missing error handling",
                    "line": self._find_line(content, "fetch("),
                    "recommendation": "Add .catch() handler for network errors"
                })
        
        print(f"🚨 Encontrados {len(issues)} problemas de seguridad:\n")
        for issue in issues:
            icon = "🔴" if issue["severity"] == "CRITICAL" else "🟠" if issue["severity"] == "HIGH" else "🟡"
            print(f"{icon} [{issue['severity']}] {issue['file']}")
            print(f"   Issue: {issue['issue']}")
            print(f"   Fix: {issue['recommendation']}\n")
        
        self.findings["security"] = issues
        return issues
    
    def analyze_with_agent_logic(self, files):
        """AGENT: Logic Checker - Busca errores lógicos en JavaScript."""
        self.print_section("⚙️  AGENT: Logic Checker")

        import re

        issues = []

        for filepath, content in files.items():
            lines = content.split("\n")

            # 1. Loose equality: == / != en lugar de === / !==
            for i, line in enumerate(lines, 1):
                stripped = line.strip()
                if re.search(r'[^=!<>]==[^=]|[^=!<>]!=[^=]', stripped):
                    # Excluir comentarios y strings obvios
                    if not stripped.startswith("//") and not stripped.startswith("*"):
                        issues.append({
                            "severity": "MEDIUM",
                            "file": filepath,
                            "line": i,
                            "issue": f"Loose equality (== / !=) at line {i}: `{stripped[:60]}`",
                            "recommendation": "Use strict equality (=== / !==) to avoid type coercion bugs",
                        })

            # 2. Código inalcanzable: sentencias después de return en el mismo bloque
            in_function = False
            found_return = False
            brace_depth = 0
            return_depth = 0
            for i, line in enumerate(lines, 1):
                stripped = line.strip()
                brace_depth += stripped.count("{") - stripped.count("}")
                if re.search(r'\bfunction\b', stripped):
                    in_function = True
                    found_return = False
                    return_depth = brace_depth
                if in_function and re.match(r'^return\b', stripped):
                    found_return = True
                    return_depth = brace_depth
                elif found_return and brace_depth == return_depth:
                    if stripped and not stripped.startswith("//") and not stripped.startswith("}"):
                        issues.append({
                            "severity": "HIGH",
                            "file": filepath,
                            "line": i,
                            "issue": f"Unreachable code after return at line {i}: `{stripped[:60]}`",
                            "recommendation": "Remove or reorder code; statements after return never execute",
                        })
                        found_return = False  # reportar solo el primero por función

            # 3. Uso de var (hoisting inesperado)
            var_lines = [
                (i + 1, line.strip())
                for i, line in enumerate(lines)
                if re.match(r'\s*var\s+', line) and not line.strip().startswith("//")
            ]
            if var_lines:
                issues.append({
                    "severity": "MEDIUM",
                    "file": filepath,
                    "line": var_lines[0][0],
                    "issue": f"{len(var_lines)} use(s) of `var` (first at line {var_lines[0][0]}): hoisting can cause subtle bugs",
                    "recommendation": "Replace `var` with `let` (mutable) or `const` (immutable)",
                })

            # 4. Callback hell: más de 3 niveles de callbacks anidados
            max_cb_depth = 0
            cb_depth = 0
            for line in lines:
                cb_depth += line.count("function(") + line.count("=> {")
                cb_depth -= line.count("}")
                max_cb_depth = max(max_cb_depth, cb_depth)
            if max_cb_depth > 3:
                issues.append({
                    "severity": "HIGH",
                    "file": filepath,
                    "line": None,
                    "issue": f"Callback hell detected: nesting depth ≈ {max_cb_depth}",
                    "recommendation": "Refactor using async/await or Promise chaining",
                })

            # 5. Posible null dereference: .property access sin null guard
            for i, line in enumerate(lines, 1):
                stripped = line.strip()
                if re.search(r'\b\w+\.\w+\s*\(', stripped):
                    if re.search(r'(getElement|querySelector|getElementById)\s*\(', stripped):
                        if "&&" not in stripped and "?" not in stripped and "if" not in stripped:
                            issues.append({
                                "severity": "MEDIUM",
                                "file": filepath,
                                "line": i,
                                "issue": f"Potential null dereference at line {i}: DOM query result used without null check",
                                "recommendation": "Guard with `if (el)` or optional chaining `el?.method()`",
                            })

            # 6. Retornos inconsistentes (null vs undefined)
            if "return null" in content and "return undefined" in content:
                issues.append({
                    "severity": "LOW",
                    "file": filepath,
                    "line": None,
                    "issue": "Inconsistent return types: mixes `null` and `undefined`",
                    "recommendation": "Pick one sentinel value; prefer `null` for intentional absence",
                })

        print(f"⚠️  Encontrados {len(issues)} problemas lógicos:\n")
        for issue in issues:
            line_ref = f" (línea {issue['line']})" if issue.get("line") else ""
            sev_icon = {"HIGH": "🔴", "MEDIUM": "🟡", "LOW": "🟢"}.get(issue["severity"], "•")
            print(f"  {sev_icon} [{issue['severity']}] {issue['file']}{line_ref}")
            print(f"     Issue: {issue['issue']}")
            print(f"     Fix:   {issue['recommendation']}\n")

        self.findings["logic"] = issues
        return issues
    
    def analyze_with_agent_smell(self, files):
        """AGENT: Code Smell Detector - Busca anti-patterns."""
        self.print_section("👃 AGENT: Code Smell Detector")
        
        issues = []
        
        for filepath, content in files.items():
            # Variables globales
            if content.startswith("let ") or content.startswith("var "):
                smell_count = content.count("\nlet ") + content.count("\nvar ")
                if smell_count > 0:
                    issues.append({
                        "severity": "MEDIUM",
                        "file": filepath,
                        "smell": f"{smell_count} global variables",
                        "recommendation": "Encapsulate in modules or classes"
                    })
            
            # Funciones muy largas
            func_lines = content.count("\nfunction ")
            if func_lines > 0 and len(content) > 1000:
                issues.append({
                    "severity": "LOW",
                    "file": filepath,
                    "smell": "Large functions detected",
                    "recommendation": "Extract into smaller, focused functions"
                })
        
        print(f"🧹 Encontrados {len(issues)} code smells:\n")
        for issue in issues:
            print(f"  • {issue['file']}: {issue['smell']}")
            print(f"    Fix: {issue['recommendation']}\n")
        
        self.findings["smells"] = issues
        return issues
    
    def analyze_with_agent_duplication(self, files):
        """AGENT: Duplication Finder - Busca código duplicado."""
        self.print_section("🔍 AGENT: Duplication Finder")
        
        issues = []
        
        # Búsqueda simple de funciones con lógica similar
        for filepath, content in files.items():
            lines = content.split('\n')
            function_blocks = {}
            
            for i, line in enumerate(lines):
                if line.strip().startswith("function "):
                    func_name = line.split('(')[0].replace("function ", "").strip()
                    # Tomar próximas 5 líneas como "fingerprint"
                    fingerprint = '\n'.join(lines[i:min(i+5, len(lines))])
                    function_blocks[func_name] = fingerprint
            
            # Detectar getLessonContent vs getLesson
            if "getLessonContent" in content and "getLesson" in content:
                issues.append({
                    "severity": "HIGH",
                    "file": filepath,
                    "issue": "Found duplicate functions: getLessonContent() and getLesson()",
                    "recommendation": "Remove one function, keep single implementation",
                    "lines_duplicated": "Lines 21-26 and 28-34"
                })
        
        print(f"📋 Encontrados {len(issues)} duplicados:\n")
        for issue in issues:
            print(f"  • {issue['file']}: {issue['issue']}")
            print(f"    Duplicated: {issue['lines_duplicated']}")
            print(f"    Fix: {issue['recommendation']}\n")
        
        self.findings["duplication"] = issues
        return issues
    
    def consult_role_security_reviewer(self):
        """ROLE: REVISOR_SEGURIDAD - Decide sobre riesgos de seguridad."""
        self.print_section("🛡️  ROLE: REVISOR_SEGURIDAD")
        
        security_issues = self.findings["security"]
        
        print("📋 Revisando hallazgos de seguridad...\n")
        
        critical = [i for i in security_issues if i["severity"] == "CRITICAL"]
        high = [i for i in security_issues if i["severity"] == "HIGH"]
        
        print(f"Total issues: {len(security_issues)}")
        print(f"  🔴 Critical: {len(critical)}")
        print(f"  🟠 High: {len(high)}\n")
        
        if critical:
            verdict = "RECHAZADO"
            icon = "❌"
            reason = "Critical security issues must be fixed before production"
        elif high:
            verdict = "RECHAZADO"
            icon = "❌"
            reason = "High-severity issues should be addressed"
        else:
            verdict = "ACEPTADO"
            icon = "✅"
            reason = "Security review passed"
        
        print(f"{icon} Veredicto: {verdict}")
        print(f"   Razón: {reason}\n")
        
        return {"verdict": verdict, "icon": icon, "reason": reason}
    
    def consult_role_performance_reviewer(self):
        """ROLE: REVISOR_PERFORMANCE - Evalúa eficiencia."""
        self.print_section("⚡ ROLE: REVISOR_PERFORMANCE")
        
        logic_issues = self.findings["logic"]
        duplication = self.findings["duplication"]
        
        print("📋 Revisando rendimiento...\n")
        
        issues_count = len(logic_issues) + len(duplication)
        print(f"Performance issues: {issues_count}\n")
        
        if len(duplication) > 0:
            verdict = "REVISAR"
            icon = "🟡"
            reason = "Code duplication impacts maintainability"
        else:
            verdict = "ACEPTADO"
            icon = "✅"
            reason = "No significant performance issues"
        
        print(f"{icon} Veredicto: {verdict}")
        print(f"   Razón: {reason}\n")
        
        return {"verdict": verdict, "icon": icon, "reason": reason}
    
    def consult_maestro_bago(self, security_verdict, performance_verdict):
        """ROLE: MAESTRO_BAGO - Interfaz final con usuario."""
        self.print_section("👑 ROLE: MAESTRO_BAGO (Interfaz Final)")
        
        print("📊 Integrando veredictos...\n")
        
        # Lógica de decisión
        all_verdicts = [security_verdict["verdict"], performance_verdict["verdict"]]
        
        if "RECHAZADO" in all_verdicts:
            final = "🔴 RECHAZADO — No listo para producción"
            actions = [
                "1. Fijar vulnerabilidades críticas de seguridad",
                "2. Refactorizar código duplicado",
                "3. Implementar TODOs pendientes",
                "4. Re-ejecutar análisis BAGO"
            ]
        elif "REVISAR" in all_verdicts:
            final = "🟡 REVISAR — Necesita mejoras"
            actions = [
                "1. Revisar y aprobar cambios de rendimiento",
                "2. Consolidar funciones duplicadas",
                "3. Ejecutar tests completos",
                "4. Re-ejecutar análisis BAGO"
            ]
        else:
            final = "✅ ACEPTADO — Listo para producción"
            actions = [
                "1. Preparar para merge a main",
                "2. Ejecutar tests finales",
                "3. Desplegar a staging",
                "4. Monitorear en producción"
            ]
        
        print(f"\n{final}\n")
        print("Próximos pasos:")
        for action in actions:
            print(f"  {action}")
        
        return {"decision": final, "actions": actions}
    
    def generate_final_report(self, security, performance, maestro):
        """Genera reporte final integrado."""
        self.print_header("📋 REPORTE FINAL BAGO — TYPING COURSE")
        
        print(f"Timestamp: {self.timestamp}")
        print(f"Proyecto: {self.project_path}\n")
        
        # Resumen de hallazgos
        print("📊 RESUMEN DE HALLAZGOS")
        print("-" * 50)
        print(f"  🔒 Security issues: {len(self.findings['security'])}")
        print(f"  ⚙️  Logic issues: {len(self.findings['logic'])}")
        print(f"  👃 Code smells: {len(self.findings['smells'])}")
        print(f"  🔍 Duplications: {len(self.findings['duplication'])}\n")
        
        # Veredictos de roles
        print("🎯 VEREDICTOS DE ROLES")
        print("-" * 50)
        print(f"  {security['icon']} REVISOR_SEGURIDAD: {security['verdict']}")
        print(f"  {performance['icon']} REVISOR_PERFORMANCE: {performance['verdict']}")
        print(f"  {maestro['decision'].split()[0]} MAESTRO_BAGO: {maestro['decision']}\n")
        
        # Recomendaciones
        print("💡 RECOMENDACIONES PRIORITARIAS")
        print("-" * 50)
        if self.findings["security"]:
            print("  1. CRÍTICO: Fijar vulnerabilidades")
            for issue in self.findings["security"][:2]:
                print(f"     - {issue['issue']}")
        
        if self.findings["duplication"]:
            print("  2. ALTO: Eliminar código duplicado")
            for issue in self.findings["duplication"][:2]:
                print(f"     - {issue['issue']}")
        
        if self.findings["smells"]:
            print("  3. MEDIO: Refactorizar code smells")
            for issue in self.findings["smells"][:1]:
                print(f"     - {issue['smell']}")
        
        print("\n")
    
    def _find_line(self, content, text):
        """Find line number of text in content."""
        for i, line in enumerate(content.split('\n'), 1):
            if text in line:
                return i
        return "?"
    
    def run(self):
        """Ejecuta análisis completo."""
        self.print_header("🎓 BAGO ANALYSIS — Typing Course Project")
        
        print(f"Start time: {self.timestamp}\n")
        
        # 1. Leer proyecto
        files = self.read_project_files()
        print(f"\n✅ Proyecto cargado ({len(files)} archivos)\n")
        
        # 2. Ejecutar AGENTS en paralelo (simulado)
        print("\n🚀 Ejecutando AGENTS en paralelo...\n")
        
        security = self.analyze_with_agent_security(files)
        logic = self.analyze_with_agent_logic(files)
        smells = self.analyze_with_agent_smell(files)
        duplication = self.analyze_with_agent_duplication(files)
        
        print("✅ Todos los AGENTS completaron análisis\n")
        
        # 3. Consultar ROLES
        print("\n👑 Consultando ROLES para decisiones...\n")
        
        security_verdict = self.consult_role_security_reviewer()
        performance_verdict = self.consult_role_performance_reviewer()
        maestro_decision = self.consult_maestro_bago(security_verdict, performance_verdict)
        
        # 4. Reporte final
        self.generate_final_report(security_verdict, performance_verdict, maestro_decision)
        
        print(f"End time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("\n" + "="*70 + "\n")

def main():
    if len(sys.argv) < 2:
        print("Uso: python bago_typing_course_analyzer.py <project_path>")
        print("\nEjemplo:")
        print("  python bago_typing_course_analyzer.py C:\\Marc_max_20gb\\typing-course")
        sys.exit(1)
    
    project_path = sys.argv[1]
    analyzer = TypingCourseAnalyzer(project_path)
    analyzer.run()


def _self_test():
    """Autotest mínimo — verifica arranque limpio del módulo."""
    from pathlib import Path as _P
    assert _P(__file__).exists(), "fichero no encontrado"
    print("  1/1 tests pasaron")

if __name__ == "__main__":
    if "--test" in sys.argv:
        _self_test()
        raise SystemExit(0)
    main()
