# BAGO Agent Factory - Documentación Completa

## Estructura de Agentes

BAGO tiene una **fábrica de agentes** con 4 especialistas base:

### Agentes Built-in

1. **security_analyzer.py** → Detecta vulnerabilidades de seguridad
   - XSS vulnerabilities
   - Hardcoded credentials
   - HTTP insecurity
   - Eval usage
   - Severity: CRITICAL, HIGH, MEDIUM

2. **logic_checker.py** → Detecta errores lógicos
   - TODOs/FIXMEs
   - Missing validation
   - Inconsistencies
   - Severity: LOW, MEDIUM

3. **smell_detector.py** → Detecta code smells
   - Global variables
   - Long functions
   - Complex conditions
   - Severity: MEDIUM, LOW

4. **duplication_finder.py** → Detecta código duplicado
   - Duplicated blocks
   - Repeated logic
   - Dead code patterns
   - Severity: LOW

---

## Agent Factory (`agent_factory.py`)

Ubicación: `.bago/agents/agent_factory.py`

### Comandos Disponibles

```bash
# Crear nuevo agente
python agent_factory.py create --name "performance_checker" --category "performance" \
  --rules "detect slow patterns" "check memory leaks" "identify bottlenecks"

# Validar estructura de agente
python agent_factory.py validate performance_checker.py

# Listar todos los agentes
python agent_factory.py list

# Obtener detalles de un agente
python agent_factory.py describe security_analyzer

# Eliminar agente
python agent_factory.py remove performance_checker
```

### Funcionamiento

La factory:
1. **Crea agentes** usando plantilla estándar
2. **Genera código ejecutable** (Python o PowerShell)
3. **Valida sintaxis** (compilable)
4. **Registra en manifest** (`.bago/agents/manifest.json`)
5. **Persiste agente** en `.bago/agents/`
6. **Permite reutilización** en próximas ejecuciones

---

## Plantilla de Agente

Ubicación: `.bago/agents/AGENT_TEMPLATE.py` (Python)

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
{name}.py — Agente BAGO generado por Factory

Categoría: {category}
Descripción: {description}

Reglas ({rules_count}):
{rules_list}

Generado: {created_at}
"""

from pathlib import Path
import ast
import json
import sys

class {class_name}(ast.NodeVisitor):
    """Agente especializado: {name}."""
    
    def __init__(self, target_path):
        self.target_path = Path(target_path)
        self.findings = []
        self.category = "{category}"
        self.agent_name = "{name}"
    
    def analyze(self):
        """Analyze target and return findings."""
        if self.target_path.is_file():
            self._analyze_file(self.target_path)
        elif self.target_path.is_dir():
            for file in self.target_path.rglob("*.{extensions}"):
                self._analyze_file(file)
        
        return {
            "agent": self.agent_name,
            "category": self.category,
            "findings": self.findings,
            "count": len(self.findings)
        }
    
    def _analyze_file(self, file_path):
        """Analyze single file."""
        try:
            content = file_path.read_text()
            # Tu lógica de análisis aquí
        except Exception as e:
            pass

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(json.dumps({"error": "Usage: {name}.py <path>"}))
        sys.exit(1)
    
    analyzer = {class_name}(sys.argv[1])
    result = analyzer.analyze()
    print(json.dumps(result))
```

---

## Manifest de Agentes

Ubicación: `.bago/agents/manifest.json`

Ejemplo:
```json
{
  "agents": {
    "security_analyzer": {
      "name": "Security Analyzer",
      "category": "security",
      "version": "1.0",
      "created": "2026-01-15T10:30:00Z",
      "status": "active",
      "rules": 5,
      "builtIn": true
    },
    "logic_checker": {
      "name": "Logic Checker",
      "category": "logic",
      "version": "1.0",
      "created": "2026-01-15T10:30:00Z",
      "status": "active",
      "rules": 5,
      "builtIn": true
    },
    "performance_checker": {
      "name": "Performance Checker",
      "category": "performance",
      "version": "1.0",
      "created": "2026-04-28T05:00:00Z",
      "status": "pending",
      "rules": 3,
      "builtIn": false
    }
  },
  "total_agents": 5,
  "by_category": {
    "security": 1,
    "logic": 1,
    "performance": 1,
    "custom": 2
  }
}
```

---

## Ciclo de Vida de un Agente

### 1. Creación

**Opción A: Via Factory CLI**
```bash
python agent_factory.py create \
  --name "performance_checker" \
  --category "performance" \
  --rules "detect slow loops" "check memory usage"
```

**Opción B: Via BAGO CLI**
```powershell
powershell .bago\bago.ps1 -Command new-agent \
  -NewAgent "performance_checker" -Category "performance"
```

Genera: `.bago/agents/performance_checker.py`

### 2. Definición (Implementación)

```python
class PerformanceChecker(ast.NodeVisitor):
    def analyze(self):
        # Implementar lógica de detección
        # Retornar hallazgos con:
        # - type (tipo de issue)
        # - severity (CRITICAL, HIGH, MEDIUM, LOW)
        # - message (descripción)
        # - suggestion (cómo arreglarlo)
```

### 3. Validación

```bash
python agent_factory.py validate performance_checker.py
```

Verifica:
- Sintaxis Python válida
- Interfaz correcta (analyze method)
- JSON output compatible
- Manejo de errores

### 4. Registro en Manifest

Factory registra automáticamente:
```json
{
  "name": "performance_checker",
  "category": "performance",
  "status": "pending",
  "rules": ["detect slow loops", "check memory usage"]
}
```

### 5. Ejecución

**Individual:**
```bash
python .bago/agents/performance_checker.py /path/to/code
```

**Via Orchestrador:**
```powershell
& .bago\code_quality_orchestrator.ps1 -TargetPath /path
```

**Via BAGO CLI:**
```powershell
powershell .bago\bago.ps1 -Command analyze -Target /path
```

### 6. Reutilización

Próximas ejecuciones: agente se carga de manifest y se ejecuta sin recrear

---

## Categorías de Agentes

| Categoría | Propósito | Ejemplos |
|-----------|----------|----------|
| security | Detectar vulnerabilidades | XSS, SQL injection, credentials |
| logic | Detectar errores lógicos | TODOs, inconsistencias |
| performance | Detectar bottlenecks | Loops lentos, memory leaks |
| style | Detectar style issues | Naming, formatting |
| architecture | Detectar issues arquitectónicos | Coupling, cohesion |
| testing | Evaluar coverage | Coverage gaps, missing tests |
| custom | Dominios especializados | Tu propia categoría |

---

## Severidades

Cada hallazgo tiene una severidad:

| Severity | Significado | Acción |
|----------|------------|--------|
| CRITICAL | Debe arreglarse inmediatamente | Bloquea merge |
| HIGH | Debe arreglarse pronto | Requiere review |
| MEDIUM | Debería arreglarse | Advisory |
| LOW | Educativo | Sugerencia |

---

## Output Format

Todo agente DEBE retornar JSON con este formato:

```json
{
  "agent": "security_analyzer",
  "category": "security",
  "findings": [
    {
      "type": "XSS_VULNERABILITY",
      "severity": "HIGH",
      "file": "src/app.js",
      "line": 42,
      "message": "innerHTML usage detected",
      "suggestion": "Use textContent instead"
    }
  ],
  "count": 1
}
```

---

## Integración con Orchestrador

### En code_quality_orchestrator.ps1

```powershell
# Ejecutar agente individual
$result = & python .bago\agents\security_analyzer.py $TargetPath
$findings = $result | ConvertFrom-Json

# Agregar hallazgos a lista general
$all += $findings.findings
```

### En role_orchestrator.ps1

Los roles reciben hallazgos agregados:

```powershell
function Invoke-SecurityReviewer {
    param([object]$Findings)
    
    # Revisa hallazgos de seguridad
    $highCount = ($Findings | Where-Object { $_.severity -eq "HIGH" }).Count
    
    # Retorna verdict
    return @{
        role = "REVISOR_SEGURIDAD"
        status = "CONDITIONAL"  # si hay issues HIGH
        recommendation = "Fix security issues"
    }
}
```

---

## Ejemplos de Agentes Existentes

### Security Analyzer

```python
# Detecta:
- innerHTML usage (XSS)
- Hardcoded credentials
- HTTP insecurity
- eval() usage

# Retorna:
{
  "agent": "security_analyzer",
  "findings": [
    {
      "type": "XSS_VULNERABILITY",
      "severity": "HIGH",
      "message": "innerHTML usage - potential XSS",
      "suggestion": "Use textContent instead"
    }
  ]
}
```

### Logic Checker

```python
# Detecta:
- TODO comments
- FIXME markers
- Missing validations
- Inconsistent patterns

# Retorna:
{
  "agent": "logic_checker",
  "findings": [
    {
      "type": "TODO_MARKER",
      "severity": "LOW",
      "message": "TODO comment found",
      "suggestion": "Complete or remove"
    }
  ]
}
```

---

## Extensión: Crear Nuevo Agente

### Paso 1: Crear usando Factory

```bash
python role_factory.py create \
  --name "accessibility_checker" \
  --category "accessibility" \
  --rules "check ARIA attributes" "validate alt text" "check contrast ratios"
```

### Paso 2: Implementar Lógica

En `.bago/agents/accessibility_checker.py`:

```python
#!/usr/bin/env python3
"""
accessibility_checker.py — Detecta issues de accesibilidad

Categoría: accessibility
Reglas:
- ARIA attributes (role, label, etc)
- Image alt text
- Color contrast ratios
"""

import ast
import json
import sys
from pathlib import Path

class AccessibilityChecker(ast.NodeVisitor):
    def __init__(self, target_path):
        self.target_path = Path(target_path)
        self.findings = []
    
    def analyze(self):
        if self.target_path.is_file():
            self._analyze_file(self.target_path)
        
        return {
            "agent": "accessibility_checker",
            "category": "accessibility",
            "findings": self.findings,
            "count": len(self.findings)
        }
    
    def _analyze_file(self, file_path):
        content = file_path.read_text()
        
        # Check for missing alt text
        if '<img' in content and 'alt=' not in content:
            self.findings.append({
                "type": "MISSING_ALT_TEXT",
                "severity": "HIGH",
                "message": "Image missing alt attribute",
                "suggestion": "Add descriptive alt text to images"
            })
        
        # Check for missing ARIA labels
        if 'button' in content and 'aria-label' not in content:
            self.findings.append({
                "type": "MISSING_ARIA_LABEL",
                "severity": "MEDIUM",
                "message": "Button missing ARIA label",
                "suggestion": "Add aria-label for accessibility"
            })

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(json.dumps({"error": "Usage: accessibility_checker.py <path>"}))
        sys.exit(1)
    
    checker = AccessibilityChecker(sys.argv[1])
    result = checker.analyze()
    print(json.dumps(result))
```

### Paso 3: Validar

```bash
python agent_factory.py validate accessibility_checker.py
```

### Paso 4: Registrar

Automático en manifest.json

### Paso 5: Usar

```bash
# Manual
python .bago/agents/accessibility_checker.py myproject/

# Con orchestrador
powershell .bago\code_quality_orchestrator.ps1 -TargetPath myproject/
```

---

## Estructura de Archivos

```
.bago/
└── agents/
    ├── AGENT_TEMPLATE.py             ← Plantilla universal
    ├── agent_factory.py              ← Factory (crea, valida, lista)
    ├── manifest.json                 ← Registry de agentes
    ├── README.md                     ← Guía de agentes
    ├── security_analyzer.py          ← Built-in: Seguridad
    ├── logic_checker.py              ← Built-in: Lógica
    ├── smell_detector.py             ← Built-in: Code smells
    └── duplication_finder.py         ← Built-in: Duplicación
```

---

## Paralelismo

El orchestrador **puede ejecutar agentes en paralelo**:

```python
with ThreadPoolExecutor(max_workers=4) as executor:
    futures = {}
    for agent_name in self.agents:
        future = executor.submit(self._execute_agent, agent_name)
        futures[future] = agent_name
    
    for future in as_completed(futures):
        result = future.result()
        self.results[futures[future]] = result
```

**Beneficio**: 4 agentes corren simultáneamente → análisis 4x más rápido

---

## Verdicts de Agentes

Cada agente emite **hallazgos** que son consumidos por **roles**:

```
Agent → Findings (hallazgos)
         ↓
Role   → Verdict (evaluación)
         ↓
MAESTRO_BAGO → Final Status (producción-readiness)
```

---

## Integración CI/CD

Los hallazgos de agentes pueden:
1. **Bloquear merge** si CRITICAL
2. **Requerir review** si HIGH
3. **Pasar automático** si LOW/MEDIUM

```yaml
# GitHub Actions
- name: BAGO Agent Analysis
  run: |
    python .bago/agents/security_analyzer.py ${{ github.workspace }}
    python .bago/agents/logic_checker.py ${{ github.workspace }}
    # Si hay CRITICAL → exit 1
```

---

## Troubleshooting

| Problema | Causa | Solución |
|----------|-------|----------|
| Agent no ejecuta | Python no en PATH | Usar PowerShell wrapper |
| No hay hallazgos | Patrón regex incorrecto | Ajustar reglas en agente |
| Agente lento | Analiza muchos archivos | Filtrar por extensión |
| Manifest corrupto | Error durante actualización | Recrear manifest.json |

---

**Conclusión**: La fábrica de agentes de BAGO proporciona un sistema extensible para crear especialistas que detectan issues específicos. Cada agente tiene responsabilidades claras, emite hallazgos estructurados y se ejecuta en paralelo para máxima eficiencia.
